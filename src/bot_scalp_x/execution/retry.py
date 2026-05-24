"""Exponential backoff retry + idempotency key guard via Redis."""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger(__name__)

_IDEMPOTENCY_TTL = 300  # 5 minutes


class RetryGuard:
    def __init__(self, redis: aioredis.Redis, max_attempts: int = 3) -> None:
        self._r = redis
        self._max = max_attempts

    def _key(self, idempotency_key: str) -> str:
        return f"order:idempotency:{idempotency_key}"

    async def is_duplicate(self, idempotency_key: str) -> bool:
        val = await self._r.get(self._key(idempotency_key))
        return val is not None

    async def mark_submitted(self, idempotency_key: str, state: str = "SUBMITTED") -> None:
        await self._r.set(self._key(idempotency_key), state, ex=_IDEMPOTENCY_TTL)

    async def mark_filled(self, idempotency_key: str) -> None:
        await self._r.set(self._key(idempotency_key), "FILLED", ex=_IDEMPOTENCY_TTL)

    async def execute_with_retry(self, fn, *args, idempotency_key: str, **kwargs):
        """Call fn(*args, **kwargs) with exponential backoff. Idempotency-safe."""
        if await self.is_duplicate(idempotency_key):
            log.warning("duplicate_order_blocked", key=idempotency_key)
            return None

        await self.mark_submitted(idempotency_key)
        delay = 1.0
        last_exc: Exception | None = None

        for attempt in range(1, self._max + 1):
            try:
                result = await fn(*args, **kwargs)
                return result
            except Exception as exc:
                last_exc = exc
                log.warning("order_attempt_failed", attempt=attempt, error=str(exc))
                if attempt < self._max:
                    await asyncio.sleep(delay)
                    delay *= 2

        raise RuntimeError(f"All {self._max} attempts failed") from last_exc
