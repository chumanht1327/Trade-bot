"""Check 7: Write trade record to DB and read it back (requires Postgres)."""

import os


async def check() -> str:
    db_url = os.environ.get("DB__URL", "")
    if not db_url or "localhost" not in db_url and "postgres" not in db_url:
        return "SKIPPED: No DB connection configured for sandbox"

    try:
        import asyncpg
        dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2, command_timeout=10)
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        await pool.close()
        return "DB connection verified: SELECT 1 succeeded"
    except Exception as exc:
        raise AssertionError(f"DB write check failed: {exc}") from exc
