"""Consecutive loss counter backed by Redis. Resets on any profitable trade."""

from __future__ import annotations

import redis.asyncio as aioredis

_KEY = "risk:losses:consecutive"


class ConsecutiveLossTracker:
    def __init__(self, redis: aioredis.Redis, max_losses: int) -> None:
        self._r = redis
        self._max = max_losses

    async def record(self, pnl: float) -> int:
        """Record trade result. Returns current consecutive loss count."""
        if pnl < 0:
            count = await self._r.incr(_KEY)
        else:
            await self._r.set(_KEY, 0)
            count = 0
        return int(count)

    async def get_count(self) -> int:
        val = await self._r.get(_KEY)
        return int(val) if val else 0

    async def set_count(self, count: int) -> None:
        """Used for state restoration from DB on restart."""
        await self._r.set(_KEY, count)

    async def is_breached(self) -> bool:
        return await self.get_count() >= self._max
