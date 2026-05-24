"""Phase 8: detect → classify → apply fix → rerun. Max 10 iterations."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import structlog

from tests.sandbox.auto_fix.classifier import classify_failure
from tests.sandbox.sanity_suite import run_all_checks, write_report

log = structlog.get_logger(__name__)

_MAX_ITERATIONS = 10
_REPORT_PATH = Path("sanity_report.json")


async def run_fix_loop() -> int:
    """
    Returns 0 on all GREEN, 1 if max iterations hit without passing.
    """
    for iteration in range(1, _MAX_ITERATIONS + 1):
        log.info("fix_loop_iteration", iteration=iteration, max=_MAX_ITERATIONS)

        results = await run_all_checks()
        write_report(results)

        failures = [r for r in results if not r.passed]
        if not failures:
            log.info("fix_loop_all_green", iterations=iteration)
            return 0

        log.warning("fix_loop_failures", count=len(failures), names=[f.name for f in failures])

        for failure in failures:
            strategy = classify_failure(failure.name, failure.details)
            fix_fn = _get_fixer(strategy)
            fix_result = await fix_fn(failure.name, failure.details)
            log.info("fix_applied", check=failure.name, strategy=strategy, result=fix_result)

    log.error("fix_loop_max_iterations_reached", iterations=_MAX_ITERATIONS)
    return 1


def _get_fixer(strategy: str):
    if strategy == "connection":
        from tests.sandbox.auto_fix.fixers.connection_fixer import fix
    elif strategy == "schema":
        from tests.sandbox.auto_fix.fixers.schema_fixer import fix
    else:
        from tests.sandbox.auto_fix.fixers.config_fixer import fix
    return fix


if __name__ == "__main__":
    from bot_scalp_x.logging_config import configure_logging
    configure_logging("INFO", "console")
    raise SystemExit(asyncio.run(run_fix_loop()))
