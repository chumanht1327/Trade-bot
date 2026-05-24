"""Initialize database: apply Alembic migrations and verify schema."""

import asyncio
import subprocess
import sys

import structlog

from bot_scalp_x.logging_config import configure_logging

configure_logging("INFO", "console")
log = structlog.get_logger(__name__)


async def verify_connection() -> None:
    from bot_scalp_x.database.connection import get_pool, close_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        log.info("db_tables_found", count=result)
    await close_pool()


def main() -> None:
    log.info("db_init_starting")
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=False)
    if result.returncode != 0:
        log.error("alembic_migration_failed")
        sys.exit(1)
    asyncio.run(verify_connection())
    log.info("db_init_complete")


if __name__ == "__main__":
    main()
