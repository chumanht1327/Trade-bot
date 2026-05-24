"""Async execution engine: coordinates routing → retry → fill → DB write."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import asyncpg
import redis.asyncio as aioredis
import structlog

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.database.repositories import trade_repo
from bot_scalp_x.execution.fill_handler import FillHandler
from bot_scalp_x.execution.order_router import route_order
from bot_scalp_x.execution.retry import RetryGuard
from bot_scalp_x.execution.schemas import (
    ExecutionReport,
    Fill,
    Order,
    OrderStatus,
    OrderType,
)
from bot_scalp_x.execution.slippage_tracker import SlippageTracker
from bot_scalp_x.gateway.schemas import MT5OrderResult
from bot_scalp_x.risk.schemas import RiskDecision
from bot_scalp_x.signals.schemas import TradeSignal

log = structlog.get_logger(__name__)


class ExecutionEngine:
    def __init__(
        self,
        gateway: object,
        pool: asyncpg.Pool,
        redis: aioredis.Redis,
    ) -> None:
        self._gw = gateway
        self._pool = pool
        self._retry = RetryGuard(redis)
        self._slippage = SlippageTracker(redis)

    async def submit(self, decision: RiskDecision, features: FeatureRow) -> ExecutionReport:
        signal = decision.signal
        idem_key = f"{signal.symbol}:{signal.direction.value}:{signal.ts.isoformat()}"

        if await self._retry.is_duplicate(idem_key):
            log.warning("duplicate_signal_blocked", symbol=signal.symbol, key=idem_key)
            raise ValueError(f"Duplicate order blocked: {idem_key}")

        order_type = route_order(decision, features)
        order = Order(
            id=uuid.uuid4(),
            symbol=signal.symbol,
            direction=signal.direction,
            order_type=order_type,
            lot_size=decision.lot_size,
            sl_price=decision.sl_price,
            tp_price=decision.tp_price,
            idempotency_key=idem_key,
            limit_price=(
                features.tick.ask if signal.direction.value == "LONG" and order_type == OrderType.LIMIT
                else features.tick.bid if order_type == OrderType.LIMIT else None
            ),
            signal_id=signal.signal_id,
        )

        report = ExecutionReport(order=order, status=OrderStatus.PENDING)

        # Write pending trade to DB before touching MT5
        expected_price = float(features.tick.mid)
        trade_id = await trade_repo.insert_trade(
            self._pool,
            {
                "external_id": str(order.id),
                "symbol": order.symbol,
                "signal_id": order.signal_id,
                "direction": order.direction.value,
                "sl_price": float(order.sl_price),
                "tp_price": float(order.tp_price),
                "lot_size": order.lot_size,
                "risk_pct": decision.risk_pct,
                "status": "PENDING",
                "open_ts": datetime.now(tz=timezone.utc),
            },
        )
        report.trade_id = trade_id

        t0 = time.monotonic()
        try:
            result: MT5OrderResult = await self._retry.execute_with_retry(
                self._gw.place_order,  # type: ignore[attr-defined]
                order,
                idempotency_key=idem_key,
            )
        except Exception as exc:
            report.status = OrderStatus.FAILED
            report.error = str(exc)
            report.latency_ms = (time.monotonic() - t0) * 1000
            await trade_repo.update_trade_status(self._pool, trade_id, status="FAILED")
            log.error("order_failed", symbol=order.symbol, error=str(exc))
            return report

        latency_ms = (time.monotonic() - t0) * 1000
        report.latency_ms = latency_ms
        report.mt5_ticket = result.ticket
        report.attempts = 1

        if result.success:
            handler = FillHandler(report)
            handler.apply_fill(Decimal(str(result.price)), result.volume)
            slippage = await self._slippage.record(
                order.symbol,
                Decimal(str(expected_price)),
                Decimal(str(result.price)),
                order.direction.value,
            )
            report.slippage_pts = slippage
            await self._retry.mark_filled(idem_key)
            await trade_repo.update_trade_status(
                self._pool, trade_id,
                status="OPEN",
                entry_price=result.price,
                slippage_pts=slippage,
            )
        else:
            report.status = OrderStatus.REJECTED
            report.error = f"MT5 retcode {result.retcode}"
            await trade_repo.update_trade_status(self._pool, trade_id, status="REJECTED")

        log.info(
            "order_executed",
            symbol=order.symbol,
            direction=order.direction.value,
            status=report.status.value,
            ticket=report.mt5_ticket,
            latency_ms=round(latency_ms, 2),
        )
        return report
