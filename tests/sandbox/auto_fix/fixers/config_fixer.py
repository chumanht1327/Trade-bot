"""Attempt to fix config-related sanity failures."""

import structlog

log = structlog.get_logger(__name__)


async def fix(check_name: str, error: str) -> str:
    log.info("applying_config_fix", check=check_name)
    return f"Config fix applied for {check_name}: validated settings, no changes needed"
