"""Check 8: Emit a Prometheus metric and verify it appears in the registry."""

from prometheus_client import CollectorRegistry, Counter, generate_latest


async def check() -> str:
    registry = CollectorRegistry()
    test_counter = Counter(
        "sanity_check_telemetry_total",
        "Telemetry sanity check counter",
        registry=registry,
    )
    test_counter.inc(1)
    output = generate_latest(registry).decode()
    assert "sanity_check_telemetry_total" in output, "Metric not found in Prometheus output"
    assert 'sanity_check_telemetry_total_total 1.0' in output or '1.0' in output
    return "Prometheus metric emitted and verified in registry output"
