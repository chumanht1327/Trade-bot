"""Signal audit trail persistence."""

from __future__ import annotations

import asyncpg


async def insert_signal(pool: asyncpg.Pool, signal: dict) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO signals (
                symbol, ts, ema_pullback, vwap_rejection, momentum_break,
                votes, direction, confidence, regime, acted_on
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id
            """,
            signal["symbol"],
            signal["ts"],
            signal.get("ema_pullback"),
            signal.get("vwap_rejection"),
            signal.get("momentum_break"),
            signal.get("votes"),
            signal.get("direction"),
            signal.get("confidence"),
            signal.get("regime"),
            signal.get("acted_on", False),
        )
    return row["id"]  # type: ignore[index]


async def mark_signal_acted_on(pool: asyncpg.Pool, signal_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE signals SET acted_on = TRUE WHERE id = $1", signal_id)


async def get_recent_signals(pool: asyncpg.Pool, symbol: str, limit: int = 50) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM signals WHERE symbol = $1 ORDER BY ts DESC LIMIT $2",
            symbol, limit,
        )
    return [dict(r) for r in rows]
