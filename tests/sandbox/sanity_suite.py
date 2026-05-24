"""Phase 7: Runs all sanity checks and writes sanity_report.json."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import structlog

from bot_scalp_x.logging_config import configure_logging

configure_logging("INFO", "console")
log = structlog.get_logger(__name__)

_REPORT_PATH = Path("sanity_report.json")


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    elapsed_ms: float


async def _run_check(name: str, coro) -> CheckResult:
    t0 = time.monotonic()
    try:
        details = await coro
        elapsed = (time.monotonic() - t0) * 1000
        log.info("check_passed", name=name, elapsed_ms=round(elapsed, 1))
        return CheckResult(name, True, str(details or "OK"), round(elapsed, 1))
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        log.error("check_failed", name=name, error=str(exc))
        return CheckResult(name, False, str(exc), round(elapsed, 1))


async def run_all_checks() -> list[CheckResult]:
    from tests.sandbox.checks.check_mt5_connection import check as mt5_conn
    from tests.sandbox.checks.check_order_placement import check as order_place
    from tests.sandbox.checks.check_order_cancel import check as order_cancel
    from tests.sandbox.checks.check_sl_tp import check as sl_tp
    from tests.sandbox.checks.check_spread_filter import check as spread_filter
    from tests.sandbox.checks.check_kill_switch import check as kill_switch
    from tests.sandbox.checks.check_db_write import check as db_write
    from tests.sandbox.checks.check_telemetry import check as telemetry
    from tests.sandbox.checks.check_restart_recovery import check as restart_recovery
    from tests.sandbox.checks.check_duplicate_prevention import check as dupe_prevention

    return [
        await _run_check("mt5_connection", mt5_conn()),
        await _run_check("order_placement", order_place()),
        await _run_check("order_cancel", order_cancel()),
        await _run_check("sl_tp_verification", sl_tp()),
        await _run_check("spread_filter", spread_filter()),
        await _run_check("kill_switch", kill_switch()),
        await _run_check("db_write", db_write()),
        await _run_check("telemetry_write", telemetry()),
        await _run_check("restart_recovery", restart_recovery()),
        await _run_check("duplicate_prevention", dupe_prevention()),
    ]


def write_report(results: list[CheckResult]) -> None:
    all_passed = all(r.passed for r in results)
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "all_passed": all_passed,
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "checks": [asdict(r) for r in results],
    }
    _REPORT_PATH.write_text(json.dumps(report, indent=2))
    status = "ALL GREEN" if all_passed else "FAILED"
    log.info("sanity_report_written", status=status, path=str(_REPORT_PATH))


async def main() -> int:
    results = await run_all_checks()
    write_report(results)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
