"""All Prometheus metric definitions. Import this module to register metrics."""

from prometheus_client import Counter, Gauge, Histogram

# ── Execution ─────────────────────────────────────────────────────────────────
order_latency_ms = Histogram(
    "order_latency_ms",
    "Order round-trip latency in milliseconds",
    ["symbol", "order_type"],
    buckets=[10, 25, 50, 100, 150, 250, 500, 1000],
)

orders_total = Counter(
    "orders_total",
    "Total orders submitted",
    ["symbol", "direction", "status"],
)

slippage_pts = Histogram(
    "slippage_pts",
    "Slippage in points (positive = adverse)",
    ["symbol"],
    buckets=[-5, -2, -1, -0.5, 0, 0.5, 1, 2, 5],
)

partial_fills_total = Counter(
    "partial_fills_total",
    "Partial fill events received",
    ["symbol"],
)

# ── Risk ──────────────────────────────────────────────────────────────────────
daily_drawdown_pct = Gauge(
    "daily_drawdown_pct",
    "Current daily drawdown percentage",
    ["date"],
)

weekly_drawdown_pct = Gauge(
    "weekly_drawdown_pct",
    "Current weekly drawdown percentage",
    ["week"],
)

consecutive_losses = Gauge(
    "consecutive_losses",
    "Current consecutive losing trade count",
)

kill_switch_active = Gauge(
    "kill_switch_active",
    "1 if kill switch is engaged, 0 otherwise",
)

# ── Signals ───────────────────────────────────────────────────────────────────
signals_evaluated_total = Counter(
    "signals_evaluated_total",
    "Signal evaluations completed",
    ["symbol", "result"],  # result: LONG, SHORT, NO_SIGNAL
)

regime_gauge = Gauge(
    "regime_current",
    "Current regime (1=TREND, 2=RANGE, 3=HIGH_VOL, 4=LOW_VOL)",
    ["symbol", "regime"],
)

# ── Data Pipeline ─────────────────────────────────────────────────────────────
ticks_ingested_total = Counter(
    "ticks_ingested_total",
    "Total ticks received from gateway",
    ["symbol"],
)

feature_compute_ms = Histogram(
    "feature_compute_ms",
    "Feature computation latency in milliseconds",
    ["symbol"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 25],
)

spread_pts_gauge = Gauge(
    "spread_pts",
    "Current spread in points",
    ["symbol"],
)
