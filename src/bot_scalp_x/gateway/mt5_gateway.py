"""Real MT5 gateway. Wraps synchronous MetaTrader5 calls in run_in_executor."""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable, Awaitable

import structlog

from bot_scalp_x.gateway.schemas import MT5AccountInfo, MT5OrderResult, MT5SymbolInfo

log = structlog.get_logger(__name__)

# MetaTrader5 only installs on Windows; import guarded at runtime
if sys.platform == "win32":
    try:
        import MetaTrader5 as mt5  # type: ignore[import]
    except ImportError:
        mt5 = None  # type: ignore[assignment]
else:
    mt5 = None  # type: ignore[assignment]


def _require_mt5() -> Any:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package is only available on Windows.")
    return mt5


class MT5Gateway:
    """Real MT5 connection. All MT5 calls run in a thread executor to avoid blocking the event loop."""

    def __init__(self, login: int, password: str, server: str, timeout_ms: int = 60000) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._timeout = timeout_ms
        self._loop: asyncio.AbstractEventLoop | None = None

    async def _run(self, fn: Callable, *args: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn, *args)

    async def connect(self) -> bool:
        lib = _require_mt5()
        ok = await self._run(
            lib.initialize,
            login=self._login,
            password=self._password,
            server=self._server,
            timeout=self._timeout,
        )
        if not ok:
            log.error("mt5_connect_failed", error=lib.last_error())
        return bool(ok)

    async def get_account_info(self) -> MT5AccountInfo:
        lib = _require_mt5()
        info = await self._run(lib.account_info)
        return MT5AccountInfo(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            currency=info.currency,
            leverage=info.leverage,
            server=info.server,
        )

    async def get_symbol_info(self, symbol: str) -> MT5SymbolInfo:
        lib = _require_mt5()
        info = await self._run(lib.symbol_info, symbol)
        tick = await self._run(lib.symbol_info_tick, symbol)
        return MT5SymbolInfo(
            name=symbol,
            bid=tick.bid,
            ask=tick.ask,
            spread=info.spread,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            point=info.point,
            digits=info.digits,
        )

    async def place_order(self, order: object) -> MT5OrderResult:  # type: ignore[override]
        from bot_scalp_x.execution.schemas import Order, OrderType
        lib = _require_mt5()
        o: Order = order  # type: ignore[assignment]

        action = lib.TRADE_ACTION_DEAL
        order_type = (
            lib.ORDER_TYPE_BUY if o.direction.value == "LONG" else lib.ORDER_TYPE_SELL
        )
        if o.order_type == OrderType.LIMIT:
            action = lib.TRADE_ACTION_PENDING
            order_type = (
                lib.ORDER_TYPE_BUY_LIMIT if o.direction.value == "LONG" else lib.ORDER_TYPE_SELL_LIMIT
            )

        request = {
            "action": action,
            "symbol": o.symbol,
            "volume": float(o.lot_size),
            "type": order_type,
            "sl": float(o.sl_price),
            "tp": float(o.tp_price),
            "deviation": 10,
            "magic": 20260101,
            "comment": o.idempotency_key[:31],
            "type_time": lib.ORDER_TIME_GTC,
            "type_filling": lib.ORDER_FILLING_IOC,
        }
        if o.limit_price is not None:
            request["price"] = float(o.limit_price)

        result = await self._run(lib.order_send, request)
        return MT5OrderResult(
            ticket=result.order,
            price=result.price,
            volume=result.volume,
            comment=result.comment,
            retcode=result.retcode,
        )

    async def cancel_order(self, ticket: int) -> bool:
        lib = _require_mt5()
        request = {"action": lib.TRADE_ACTION_REMOVE, "order": ticket}
        result = await self._run(lib.order_send, request)
        return result.retcode == lib.TRADE_RETCODE_DONE

    async def get_open_positions(self) -> list[dict]:
        lib = _require_mt5()
        positions = await self._run(lib.positions_get) or []
        return [p._asdict() for p in positions]

    async def subscribe_ticks(self, symbol: str, callback: Callable) -> None:
        """Real MT5 tick streaming via polling (MT5 has no push-based async tick API)."""
        lib = _require_mt5()
        log.info("mt5_tick_polling_starting", symbol=symbol)
        last_ts = 0
        while True:
            tick = await self._run(lib.symbol_info_tick, symbol)
            if tick and tick.time > last_ts:
                last_ts = tick.time
                from datetime import datetime, timezone
                from decimal import Decimal
                from bot_scalp_x.data.schemas import Tick
                t = Tick(
                    symbol=symbol,
                    ts=datetime.fromtimestamp(tick.time, tz=timezone.utc),
                    bid=Decimal(str(tick.bid)),
                    ask=Decimal(str(tick.ask)),
                    volume=float(tick.volume),
                )
                await callback(t)
            await asyncio.sleep(0.05)
