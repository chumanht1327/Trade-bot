"""Trade lifecycle persistence."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import asyncpg


async def insert_trade(pool: asyncpg.Pool, trade: dict) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO trades (
                external_id, symbol, signal_id, direction, entry_price,
                sl_price, tp_price, lot_size, risk_pct, status,
                open_ts, fills_json
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            RETURNING id
            """,
            trade.get("external_id"),
            trade["symbol"],
            trade.get("signal_id"),
            trade["direction"],
            trade.get("entry_price"),
            trade.get("sl_price"),
            trade.get("tp_price"),
            trade.get("lot_size"),
            trade.get("risk_pct"),
            trade["status"],
            trade.get("open_ts", datetime.utcnow()),
            json.dumps(trade.get("fills", [])),
        )
    return row["id"]  # type: ignore[index]


async def update_trade_status(pool: asyncpg.Pool, trade_id: int, **kwargs: object) -> None:
    allowed = {"status", "close_ts", "close_price", "realized_pnl", "slippage_pts", "fills_json"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE trades SET {sets} WHERE id = $1",
            trade_id, *values,
        )


async def get_trade(pool: asyncpg.Pool, trade_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM trades WHERE id = $1", trade_id)
    return dict(row) if row else None


async def get_open_trades(pool: asyncpg.Pool, symbol: str | None = None) -> list[dict]:
    async with pool.acquire() as conn:
        if symbol:
            rows = await conn.fetch(
                "SELECT * FROM trades WHERE status IN ('OPEN','PARTIAL') AND symbol = $1 ORDER BY open_ts",
                symbol,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM trades WHERE status IN ('OPEN','PARTIAL') ORDER BY open_ts"
            )
    return [dict(r) for r in rows]
