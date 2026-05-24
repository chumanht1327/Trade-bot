"""asyncpg connection pool factory."""

from __future__ import annotations

import asyncpg

from bot_scalp_x.config import get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        # Strip SQLAlchemy prefix for raw asyncpg
        dsn = settings.db.url.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=settings.db.pool_size,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
