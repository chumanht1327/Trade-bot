"""Slippage tracking: expected vs actual fill price, logged to Redis and metrics."""

from __future__ import annotations

from decimal import Decimal

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger(__name__)

_MAX_HISTORY = 1000
_TTL = 3600  # 1 hour


class SlippageTracker:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def record(self, symbol: str, expected: Decimal, actual: Decimal, direction: str) -> float:
        """Record slippage in points. Positive = adverse slippage."""
        from bot_scalp_x.signals.schemas import Direction
        pts = float(actual - expected)
        if direction == Direction.LONG.value:
            pts = -pts  # Paid more than expected on buy = adverse

        key = f"metrics:latency:{symbol}"
        await self._r.lpush(key, pts)
        await self._r.ltrim(key, 0, _MAX_HISTORY - 1)
        await self._r.expire(key, _TTL)

        log.info("slippage_recorded", symbol=symbol, direction=direction,
                 expected=str(expected), actual=str(actual), slippage_pts=round(pts, 5))
        return pts

    async def get_average(self, symbol: str) -> float:
        raw = await self._r.lrange(f"metrics:latency:{symbol}", 0, 99)
        if not raw:
            return 0.0
        return sum(float(v) for v in raw) / len(raw)
