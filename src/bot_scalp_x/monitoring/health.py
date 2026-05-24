"""Health and readiness check endpoints."""

from __future__ import annotations

import asyncpg
import redis.asyncio as aioredis


async def check_postgres(pool: asyncpg.Pool) -> bool:
    try:
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def check_redis(redis: aioredis.Redis) -> bool:
    try:
        return await redis.ping()
    except Exception:
        return False


async def readiness_check(pool: asyncpg.Pool, redis: aioredis.Redis) -> dict:
    pg_ok = await check_postgres(pool)
    redis_ok = await check_redis(redis)
    healthy = pg_ok and redis_ok
    return {
        "status": "ok" if healthy else "degraded",
        "postgres": "ok" if pg_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }
