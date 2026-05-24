"""Redis ring buffer for recent ticks. Writes latest tick hash and bounded list."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import redis.asyncio as aioredis

from bot_scalp_x.data.schemas import Tick

_MAX_BUFFER = 10_000
_LATEST_TTL = 10  # seconds


class TickBuffer:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def push(self, tick: Tick) -> None:
        payload = json.dumps(
            {
                "symbol": tick.symbol,
                "ts": tick.ts.isoformat(),
                "bid": str(tick.bid),
                "ask": str(tick.ask),
                "volume": tick.volume,
            }
        )
        async with self._r.pipeline(transaction=False) as pipe:
            # Latest tick hash
            pipe.hset(
                f"tick:latest:{tick.symbol}",
                mapping={
                    "bid": str(tick.bid),
                    "ask": str(tick.ask),
                    "spread": str(tick.spread_pts),
                    "ts": tick.ts.isoformat(),
                },
            )
            pipe.expire(f"tick:latest:{tick.symbol}", _LATEST_TTL)
            # Ring buffer list
            pipe.lpush(f"tick:buffer:{tick.symbol}", payload)
            pipe.ltrim(f"tick:buffer:{tick.symbol}", 0, _MAX_BUFFER - 1)
            await pipe.execute()

    async def get_latest(self, symbol: str) -> Tick | None:
        data = await self._r.hgetall(f"tick:latest:{symbol}")
        if not data:
            return None
        return Tick(
            symbol=symbol,
            ts=datetime.fromisoformat(data[b"ts"].decode()),
            bid=Decimal(data[b"bid"].decode()),
            ask=Decimal(data[b"ask"].decode()),
        )

    async def get_buffer(self, symbol: str, count: int = 100) -> list[Tick]:
        raw = await self._r.lrange(f"tick:buffer:{symbol}", 0, count - 1)
        ticks = []
        for r in raw:
            d = json.loads(r)
            ticks.append(
                Tick(
                    symbol=d["symbol"],
                    ts=datetime.fromisoformat(d["ts"]),
                    bid=Decimal(d["bid"]),
                    ask=Decimal(d["ask"]),
                    volume=d["volume"],
                )
            )
        return ticks
