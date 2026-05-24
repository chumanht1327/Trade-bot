"""Drawdown snapshot persistence for kill switch state recovery on restart."""

from __future__ import annotations

from datetime import date

import asyncpg


async def upsert_snapshot(pool: asyncpg.Pool, snapshot: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO drawdown_snapshots (
                snapshot_date, snapshot_week, daily_dd_pct, weekly_dd_pct,
                equity_start, equity_current, consecutive_losses, kill_switch_active
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (snapshot_date) DO UPDATE SET
                daily_dd_pct = EXCLUDED.daily_dd_pct,
                weekly_dd_pct = EXCLUDED.weekly_dd_pct,
                equity_current = EXCLUDED.equity_current,
                consecutive_losses = EXCLUDED.consecutive_losses,
                kill_switch_active = EXCLUDED.kill_switch_active
            """,
            snapshot["snapshot_date"],
            snapshot["snapshot_week"],
            snapshot.get("daily_dd_pct", 0.0),
            snapshot.get("weekly_dd_pct", 0.0),
            snapshot.get("equity_start", 0.0),
            snapshot.get("equity_current", 0.0),
            snapshot.get("consecutive_losses", 0),
            snapshot.get("kill_switch_active", False),
        )


async def get_latest_snapshot(pool: asyncpg.Pool) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM drawdown_snapshots ORDER BY snapshot_date DESC LIMIT 1"
        )
    return dict(row) if row else None


async def get_snapshot_for_date(pool: asyncpg.Pool, d: date) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM drawdown_snapshots WHERE snapshot_date = $1", d
        )
    return dict(row) if row else None
