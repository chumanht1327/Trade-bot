"""Check 5: Simulate spread > threshold → verify rejection."""

from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from bot_scalp_x.risk.kill_switch import KillSwitch


async def check() -> str:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    ks = KillSwitch(redis, max_latency_ms=150.0)
    # XAUUSD max spread is 3.0 points; simulate 5.0
    triggered = await ks.check_spread(5.0, max_spread=3.0, symbol="XAUUSD")
    assert triggered, "Expected spread filter to trigger kill switch"
    redis.set.assert_called()
    return "Spread filter correctly triggered at 5.0 pts (limit 3.0)"
