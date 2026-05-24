"""Maps sanity check failure patterns to fix strategies."""

from __future__ import annotations


FAILURE_FIX_MAP: dict[str, str] = {
    "mt5_connection": "connection",
    "db_write": "connection",
    "telemetry_write": "config",
    "kill_switch": "config",
    "spread_filter": "config",
    "restart_recovery": "config",
    "duplicate_prevention": "config",
    "order_placement": "connection",
    "order_cancel": "connection",
    "sl_tp_verification": "connection",
}


def classify_failure(check_name: str, error_detail: str) -> str:
    """Return fix strategy name for a failed check."""
    # Check name-based classification first
    strategy = FAILURE_FIX_MAP.get(check_name, "config")

    # Override based on error content
    if "Connection" in error_detail or "refused" in error_detail.lower():
        strategy = "connection"
    elif "schema" in error_detail.lower() or "column" in error_detail.lower():
        strategy = "schema"

    return strategy
