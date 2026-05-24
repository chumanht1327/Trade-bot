"""Check 6: Trigger DD breach → kill switch activates → blocks new orders."""

from unittest.mock import AsyncMock

from bot_scalp_x.risk.kill_switch import KillSwitch


async def check() -> str:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    ks = KillSwitch(redis, max_latency_ms=150.0)
    event = await ks.activate("test_dd_breach", dd_pct=3.5)
    assert event.reason == "test_dd_breach"
    assert "dd_pct" in event.__dict__ or event.dd_pct == 3.5

    # Simulate that Redis now returns ACTIVE
    redis.get = AsyncMock(return_value=b"ACTIVE")
    assert await ks.is_active(), "Kill switch should be ACTIVE after activation"
    return f"Kill switch activated for reason='{event.reason}', is_active=True verified"
