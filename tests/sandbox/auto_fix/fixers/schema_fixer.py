"""Attempt to fix schema-related sanity failures via alembic migrate."""

import subprocess
import structlog

log = structlog.get_logger(__name__)


async def fix(check_name: str, error: str) -> str:
    log.info("applying_schema_fix", check=check_name)
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return f"Schema fix applied: alembic upgrade head succeeded"
        return f"Schema fix attempted but alembic failed: {result.stderr[:200]}"
    except Exception as exc:
        return f"Schema fix could not run alembic: {exc}"
