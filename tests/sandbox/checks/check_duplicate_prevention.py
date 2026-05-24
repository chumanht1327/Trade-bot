"""Check 10: Submit same order twice; verify second blocked by idempotency key."""

from unittest.mock import AsyncMock


async def check() -> str:
    from bot_scalp_x.execution.retry import RetryGuard

    redis = AsyncMock()
    call_count = {"n": 0}

    async def mock_get(key):
        return b"SUBMITTED" if call_count["n"] > 0 else None

    redis.get = mock_get
    redis.set = AsyncMock(side_effect=lambda *a, **kw: call_count.update({"n": call_count["n"] + 1}))

    guard = RetryGuard(redis, max_attempts=3)
    idem_key = "sandbox_dupe_check_xauusd_long"

    # First call: not duplicate
    is_dupe_first = await guard.is_duplicate(idem_key)
    assert not is_dupe_first, "First call should NOT be duplicate"

    # Mark as submitted (simulates first order going through)
    await guard.mark_submitted(idem_key)

    # Second call: should be duplicate now
    is_dupe_second = await guard.is_duplicate(idem_key)
    assert is_dupe_second, "Second call SHOULD be detected as duplicate"

    return "Duplicate prevention verified: second submission blocked by idempotency key"
