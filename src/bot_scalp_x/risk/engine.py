"""Risk engine: single evaluate() entry point gating all trade signals."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import structlog

from bot_scalp_x.config import get_settings
from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
from bot_scalp_x.risk.drawdown import DrawdownTracker
from bot_scalp_x.risk.kill_switch import KillSwitch
from bot_scalp_x.risk.position_sizer import calculate_position
from bot_scalp_x.risk.schemas import RiskDecision, RiskStatus
from bot_scalp_x.signals.schemas import TradeSignal

log = structlog.get_logger(__name__)


class RiskEngine:
    def __init__(
        self,
        kill_switch: KillSwitch,
        drawdown: DrawdownTracker,
        loss_tracker: ConsecutiveLossTracker,
    ) -> None:
        self._ks = kill_switch
        self._dd = drawdown
        self._loss = loss_tracker
        self._cfg = get_settings().risk

    async def evaluate(
        self,
        signal: TradeSignal,
        features: FeatureRow,
        account_equity: float,
    ) -> RiskDecision:
        spread_pts = float(features.tick.spread_pts)
        max_spread = self._cfg.max_spread_for(signal.symbol)
        risk_pct = self._cfg.risk_per_trade_pct

        # 1. Kill switch
        if await self._ks.is_active():
            return RiskDecision(signal, RiskStatus.REJECTED_KILL_SWITCH, None, None, None, risk_pct,
                                "Kill switch is active")

        # 2. Spread check (also triggers kill switch if exceeded)
        if await self._ks.check_spread(spread_pts, max_spread, signal.symbol):
            return RiskDecision(signal, RiskStatus.REJECTED_SPREAD, None, None, None, risk_pct,
                                f"Spread {spread_pts:.3f} > max {max_spread:.3f}")

        # 3. Drawdown checks
        if await self._dd.is_daily_breached():
            await self._ks.activate("daily_dd_breached")
            return RiskDecision(signal, RiskStatus.REJECTED_DAILY_DD, None, None, None, risk_pct,
                                f"Daily DD limit {self._cfg.daily_dd_limit_pct}% breached")

        if await self._dd.is_weekly_breached():
            await self._ks.activate("weekly_dd_breached")
            return RiskDecision(signal, RiskStatus.REJECTED_WEEKLY_DD, None, None, None, risk_pct,
                                f"Weekly DD limit {self._cfg.weekly_dd_limit_pct}% breached")

        # 4. Consecutive losses
        if await self._loss.is_breached():
            return RiskDecision(signal, RiskStatus.REJECTED_CONSECUTIVE_LOSS, None, None, None, risk_pct,
                                f"Max consecutive losses ({self._cfg.max_consecutive_losses}) reached")

        # 5. Position sizing
        result = calculate_position(features, signal.direction, account_equity, risk_pct)
        if result is None:
            return RiskDecision(signal, RiskStatus.REJECTED_NO_VOLATILITY, None, None, None, risk_pct,
                                "ATR too small to compute valid position size")

        lot_size, sl_price, tp_price = result

        log.info(
            "risk_approved",
            symbol=signal.symbol,
            direction=signal.direction.value,
            lot_size=lot_size,
            sl=str(sl_price),
            tp=str(tp_price),
            risk_pct=risk_pct,
        )
        return RiskDecision(signal, RiskStatus.APPROVED, lot_size, sl_price, tp_price, risk_pct, "OK")

    async def record_trade_result(self, pnl: float, current_equity: float) -> None:
        """Called after trade closes; updates all risk state."""
        await self._loss.record(pnl)
        await self._dd.update(current_equity)
