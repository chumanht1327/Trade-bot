"""Unit tests for risk components (position sizing, kill switch, DD, consecutive loss)."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from bot_scalp_x.data.schemas import FeatureRow, Session, Tick
from bot_scalp_x.risk.position_sizer import calculate_position
from bot_scalp_x.risk.schemas import RiskStatus
from bot_scalp_x.signals.schemas import Direction
from datetime import datetime, timezone


def make_row(atr: float = 2.5, bid: float = 1984.5, ask: float = 1985.0, symbol: str = "XAUUSD") -> FeatureRow:
    tick = Tick(
        symbol=symbol,
        ts=datetime.now(tz=timezone.utc),
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        volume=5.0,
    )
    return FeatureRow(
        symbol=symbol, ts=tick.ts, tick=tick,
        atr_14=atr, vwap=1984.8, momentum_5=0.001, momentum_20=0.0005,
        liquidity_score=0.8, session=Session.LONDON, regime="TREND",
    )


class TestPositionSizer:
    def test_long_position(self):
        row = make_row(atr=2.5)
        result = calculate_position(row, Direction.LONG, 10_000.0, 0.25)
        assert result is not None
        lot_size, sl, tp = result
        assert lot_size >= 0.01
        assert sl < Decimal("1985.0")  # SL below entry for LONG
        assert tp > Decimal("1985.0")  # TP above entry

    def test_short_position(self):
        row = make_row(atr=2.5)
        result = calculate_position(row, Direction.SHORT, 10_000.0, 0.25)
        assert result is not None
        lot_size, sl, tp = result
        assert sl > Decimal("1984.5")  # SL above entry for SHORT
        assert tp < Decimal("1984.5")  # TP below entry

    def test_zero_atr_returns_none(self):
        row = make_row(atr=0.0)
        assert calculate_position(row, Direction.LONG, 10_000.0, 0.25) is None

    def test_lot_size_respects_risk_pct(self):
        row = make_row(atr=2.5)
        r1 = calculate_position(row, Direction.LONG, 10_000.0, 0.25)
        r2 = calculate_position(row, Direction.LONG, 10_000.0, 0.5)
        assert r1 is not None and r2 is not None
        # Higher risk % → larger lot size
        assert r2[0] > r1[0]

    def test_lot_capped_at_max(self):
        # Huge equity + small ATR → would be massive; should cap at 10.0
        row = make_row(atr=0.001)
        result = calculate_position(row, Direction.LONG, 10_000_000.0, 0.25)
        if result is not None:
            assert result[0] <= 10.0


@pytest.mark.asyncio
class TestKillSwitch:
    async def test_latency_triggers_kill_switch(self):
        from bot_scalp_x.risk.kill_switch import KillSwitch
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        ks = KillSwitch(redis, max_latency_ms=150.0)
        triggered = await ks.check_latency(200.0)
        assert triggered
        redis.set.assert_called()

    async def test_latency_below_threshold_does_not_trigger(self):
        from bot_scalp_x.risk.kill_switch import KillSwitch
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        ks = KillSwitch(redis, max_latency_ms=150.0)
        triggered = await ks.check_latency(100.0)
        assert not triggered

    async def test_is_active_returns_true_when_set(self):
        from bot_scalp_x.risk.kill_switch import KillSwitch
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"ACTIVE")
        ks = KillSwitch(redis, max_latency_ms=150.0)
        assert await ks.is_active()

    async def test_is_active_returns_false_when_inactive(self):
        from bot_scalp_x.risk.kill_switch import KillSwitch
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"INACTIVE")
        ks = KillSwitch(redis, max_latency_ms=150.0)
        assert not await ks.is_active()


@pytest.mark.asyncio
class TestConsecutiveLoss:
    async def test_loss_increments_counter(self):
        from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=3)
        redis.set = AsyncMock()
        tracker = ConsecutiveLossTracker(redis, max_losses=5)
        count = await tracker.record(-100.0)
        assert count == 3

    async def test_profit_resets_counter(self):
        from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
        redis = AsyncMock()
        redis.set = AsyncMock()
        tracker = ConsecutiveLossTracker(redis, max_losses=5)
        count = await tracker.record(50.0)
        assert count == 0
        redis.set.assert_called_with("risk:losses:consecutive", 0)

    async def test_breach_at_max(self):
        from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"5")
        tracker = ConsecutiveLossTracker(redis, max_losses=5)
        assert await tracker.is_breached()

    async def test_not_breached_below_max(self):
        from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"4")
        tracker = ConsecutiveLossTracker(redis, max_losses=5)
        assert not await tracker.is_breached()
