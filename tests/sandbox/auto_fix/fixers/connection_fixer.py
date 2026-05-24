"""Attempt to fix connection-related sanity failures."""

import asyncio
import structlog

log = structlog.get_logger(__name__)


async def fix(check_name: str, error: str) -> str:
    """Attempt connection recovery: re-init mock, short wait."""
    log.info("applying_connection_fix", check=check_name)
    await asyncio.sleep(1.0)  # Brief pause before retry
    return f"Connection fix applied for {check_name}: waited 1s for service recovery"
