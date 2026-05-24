"""Phase 9: Full merge gate. Runs all test suites; tags release on all GREEN."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime

import structlog

from bot_scalp_x.logging_config import configure_logging

configure_logging("INFO", "console")
log = structlog.get_logger(__name__)


def run_cmd(label: str, *cmd: str) -> bool:
    log.info("gate_running", step=label)
    result = subprocess.run(list(cmd), capture_output=False)
    passed = result.returncode == 0
    log.info("gate_step_result", step=label, passed=passed)
    return passed


async def run_gate() -> int:
    steps = [
        ("unit_tests", "pytest", "tests/unit", "-v", "-q", "--tb=short"),
        ("integration_tests", "pytest", "tests/integration", "-v", "--tb=short", "-m", "integration"),
    ]

    all_passed = True
    for label, *cmd in steps:
        if not run_cmd(label, *cmd):
            all_passed = False
            log.error("gate_step_failed", step=label)

    # Sanity suite (Phase 7 + 8)
    from tests.sandbox.auto_fix.fix_loop import run_fix_loop
    sandbox_result = await run_fix_loop()
    if sandbox_result != 0:
        all_passed = False
        log.error("gate_step_failed", step="sandbox_sanity_suite")

    if all_passed:
        # Auto-tag the release
        version = f"release-v0.1.{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        tag_result = subprocess.run(["git", "tag", version], capture_output=True)
        if tag_result.returncode == 0:
            log.info("release_tagged", version=version)
        else:
            log.warning("tagging_failed", stderr=tag_result.stderr.decode())
        log.info("merge_gate_passed")
        return 0
    else:
        log.error("merge_gate_failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_gate()))
