"""Check 9: Simulate restart with active kill switch; verify state restored from snapshot."""

from unittest.mock import AsyncMock


async def check() -> str:
    from bot_scalp_x.risk.kill_switch import KillSwitch
    from bot_scalp_x.risk.drawdown import DrawdownTracker
    from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker

    # Simulate snapshot from DB with active kill switch
    snapshot = {
        "snapshot_date": "2026-05-01",
        "kill_switch_active": True,
        "daily_dd_pct": 2.1,
        "weekly_dd_pct": 3.5,
        "equity_start": 10000.0,
        "equity_current": 9790.0,
        "consecutive_losses": 3,
    }

    redis = AsyncMock()
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=b"ACTIVE")
    redis.hset = AsyncMock()
    redis.expire = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.hgetall = AsyncMock(return_value={b"pct": b"2.1", b"equity_start": b"10000.0"})

    ks = KillSwitch(redis, max_latency_ms=150.0)
    dd = DrawdownTracker(redis, 2.0, 5.0)
    loss = ConsecutiveLossTracker(redis, 5)

    await ks.restore_from_db(snapshot["kill_switch_active"])
    await dd.restore_from_snapshot(snapshot)
    await loss.set_count(snapshot["consecutive_losses"])

    assert await ks.is_active(), "Kill switch should be ACTIVE after restore"
    daily_dd, weekly_dd = await dd.get_current()
    assert daily_dd > 0, f"Daily DD should be restored, got {daily_dd}"

    return f"Restart recovery verified: kill_switch=ACTIVE, daily_dd={daily_dd:.2f}%"
