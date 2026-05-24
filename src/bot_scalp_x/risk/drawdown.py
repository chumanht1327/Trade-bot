"""Daily/weekly drawdown tracker. Redis is the fast path; DB is authoritative on cold start."""

from __future__ import annotations

from datetime import date, datetime, timezone

import redis.asyncio as aioredis


def _daily_key(d: date) -> str:
    return f"risk:dd:daily:{d.isoformat()}"


def _weekly_key(d: date) -> str:
    monday = d - __import__("datetime").timedelta(days=d.weekday())
    return f"risk:dd:weekly:{monday.isoformat()}"


class DrawdownTracker:
    def __init__(self, redis: aioredis.Redis, daily_limit_pct: float, weekly_limit_pct: float) -> None:
        self._r = redis
        self._daily_limit = daily_limit_pct
        self._weekly_limit = weekly_limit_pct

    async def initialize_day(self, equity: float) -> None:
        today = date.today()
        key = _daily_key(today)
        await self._r.hset(key, mapping={"equity_start": equity, "pct": "0.0"})
        await self._r.expire(key, 48 * 3600)

        wkey = _weekly_key(today)
        exists = await self._r.exists(wkey)
        if not exists:
            await self._r.hset(wkey, mapping={"equity_start": equity, "pct": "0.0"})
            await self._r.expire(wkey, 8 * 86400)

    async def update(self, current_equity: float) -> tuple[float, float]:
        """Update DD percentages. Returns (daily_dd_pct, weekly_dd_pct)."""
        today = date.today()
        daily_key = _daily_key(today)
        weekly_key = _weekly_key(today)

        daily_data = await self._r.hgetall(daily_key)
        weekly_data = await self._r.hgetall(weekly_key)

        daily_start = float(daily_data.get(b"equity_start", current_equity))
        weekly_start = float(weekly_data.get(b"equity_start", current_equity))

        daily_dd = max(0.0, (daily_start - current_equity) / daily_start * 100.0)
        weekly_dd = max(0.0, (weekly_start - current_equity) / weekly_start * 100.0)

        await self._r.hset(daily_key, "pct", str(daily_dd))
        await self._r.hset(weekly_key, "pct", str(weekly_dd))

        return daily_dd, weekly_dd

    async def get_current(self) -> tuple[float, float]:
        today = date.today()
        daily_data = await self._r.hgetall(_daily_key(today))
        weekly_data = await self._r.hgetall(_weekly_key(today))
        daily_dd = float(daily_data.get(b"pct", b"0.0"))
        weekly_dd = float(weekly_data.get(b"pct", b"0.0"))
        return daily_dd, weekly_dd

    async def is_daily_breached(self) -> bool:
        daily_dd, _ = await self.get_current()
        return daily_dd >= self._daily_limit

    async def is_weekly_breached(self) -> bool:
        _, weekly_dd = await self.get_current()
        return weekly_dd >= self._weekly_limit

    async def restore_from_snapshot(self, snapshot: dict) -> None:
        """Restore Redis state from DB snapshot on cold start."""
        today = date.today()
        daily_dd = snapshot.get("daily_dd_pct", 0.0) or 0.0
        weekly_dd = snapshot.get("weekly_dd_pct", 0.0) or 0.0
        equity_start = snapshot.get("equity_start", 0.0) or 0.0

        await self._r.hset(_daily_key(today), mapping={"pct": daily_dd, "equity_start": equity_start})
        await self._r.expire(_daily_key(today), 48 * 3600)
        await self._r.hset(_weekly_key(today), mapping={"pct": weekly_dd, "equity_start": equity_start})
        await self._r.expire(_weekly_key(today), 8 * 86400)
