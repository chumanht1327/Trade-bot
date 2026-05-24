"""Bulk tick insert using PostgreSQL COPY protocol for maximum throughput."""

from __future__ import annotations

import io
from datetime import datetime

import asyncpg

from bot_scalp_x.data.schemas import Tick


async def bulk_insert_ticks(pool: asyncpg.Pool, ticks: list[Tick]) -> int:
    """COPY-based bulk insert. Returns number of rows inserted."""
    if not ticks:
        return 0

    buf = io.StringIO()
    for t in ticks:
        session = "OFF"  # Will be set by feature engine; default for raw ticks
        buf.write(
            f"{t.symbol}\t{t.ts.isoformat()}\t{t.bid}\t{t.ask}\t"
            f"{t.spread_pts}\t{t.volume}\t{session}\n"
        )
    buf.seek(0)

    async with pool.acquire() as conn:
        result = await conn.copy_to_table(
            "ticks",
            source=buf,
            columns=["symbol", "ts", "bid", "ask", "spread_pts", "volume", "session"],
            format="text",
        )
    return int(result.split()[-1]) if result else 0


async def get_ticks(
    pool: asyncpg.Pool,
    symbol: str,
    start: datetime,
    end: datetime,
    limit: int = 10_000,
) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, symbol, ts, bid, ask, spread_pts, volume, session
            FROM ticks
            WHERE symbol = $1 AND ts BETWEEN $2 AND $3
            ORDER BY ts
            LIMIT $4
            """,
            symbol, start, end, limit,
        )
    return [dict(r) for r in rows]
