# BOT-SCALP-X

AI-assisted scalping bot for **XAUUSD**, **NAS100**, and **EURUSD**.

Emphasizes execution quality, risk management, and production reliability over prediction alone. Built on a full async Python stack with MetaTrader 5 integration, PostgreSQL tick storage, Redis state management, and Prometheus/Grafana monitoring.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Infrastructure Setup](#infrastructure-setup)
7. [Database Initialization](#database-initialization)
8. [Running the Bot](#running-the-bot)
9. [Dashboard](#dashboard)
10. [Training the Regime Model](#training-the-regime-model)
11. [Backtesting](#backtesting)
12. [Sandbox Sanity Suite](#sandbox-sanity-suite)
13. [Auto-Fix Loop](#auto-fix-loop)
14. [Merge Gate](#merge-gate)
15. [Branch Strategy](#branch-strategy)
16. [Live Rollout Plan](#live-rollout-plan)
17. [Monitoring & Alerts](#monitoring--alerts)
18. [Risk Parameters Reference](#risk-parameters-reference)
19. [Signal Logic Reference](#signal-logic-reference)
20. [MT5 Gateway Modes](#mt5-gateway-modes)
21. [MQL5 Bridge](#mql5-bridge)
22. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
Market Data (MT5)
      │
      ▼
Feature Engine          ← ATR, VWAP, Momentum, Liquidity Score, Session
      │
      ▼
Regime Classifier       ← XGBoost: TREND / RANGE / HIGH_VOL / LOW_VOL
      │
      ▼
Signal Engine           ← EMA Pullback + VWAP Rejection + Momentum Breakout
   (2-of-3 vote)
      │
      ▼
Risk Engine             ← Position size, DD limits, kill switch gate
      │
      ▼
Execution Engine        ← Market/Limit routing, retry, idempotency
      │
      ▼
MT5 Gateway             ← Real (Windows) or async Mock (Linux/CI)
      │
      ▼
PostgreSQL + Redis      ← Tick storage, trade lifecycle, state
      │
      ▼
Prometheus + Grafana    ← Metrics, dashboards, alerting
```

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.11 | Match/case syntax required |
| Docker | 24.0 | For infrastructure services |
| Docker Compose | v2.20 | Bundled with Docker Desktop |
| Git | 2.x | |
| MetaTrader 5 | Any | Windows only for live trading; mock used elsewhere |

> **Linux / macOS**: The bot runs fully in mock mode (no MT5 required). All development, testing, and backtesting work without Windows.

> **Windows (live trading)**: Install the [MetaTrader5 Python package](https://pypi.org/project/MetaTrader5/) and set `MT5__MOCK_MODE=false`.

---

## Project Structure

```
Trade-bot/
├── src/bot_scalp_x/        # Core installable package
│   ├── config.py            # All settings (single source of truth)
│   ├── orchestrator.py      # Main async bot loop
│   ├── data/                # Tick ingestion, feature engine, Redis buffer
│   ├── regime/              # XGBoost regime classifier
│   ├── signals/             # EMA Pullback, VWAP Rejection, Momentum Breakout
│   ├── risk/                # Position sizer, drawdown, kill switch
│   ├── execution/           # Order routing, fill handler, retry
│   ├── gateway/             # MT5 real + mock implementations
│   ├── database/            # asyncpg pool, repositories, migrations
│   └── monitoring/          # Prometheus metrics, health endpoints
├── dashboard/               # FastAPI web dashboard
├── docker/                  # Compose, Dockerfiles, Postgres schema
├── mql5/                    # MetaTrader 5 Expert Advisor bridge
├── tests/
│   ├── unit/                # Fast, no I/O tests
│   ├── integration/         # Requires Postgres + Redis
│   ├── backtests/           # Tick-replay backtesting framework
│   ├── sandbox/             # Phase 7 sanity checks + auto-fix loop
│   └── merge_gate/          # Phase 9 full gate → release tag
├── strategy/signal_configs/ # Per-symbol YAML parameters
├── datasets/                # Raw + processed tick data (gitignored)
└── scripts/                 # CLI utilities
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/chumanht1327/Trade-bot.git
cd Trade-bot
```

### 2. Create and activate a virtual environment (recommended)

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows
```

### 3. Install the package and all dependencies

```bash
pip install -e ".[dev]"
```

For backtesting notebooks also install:

```bash
pip install -e ".[dev,backtest]"
```

---

## Configuration

### 1. Copy the example environment file

```bash
cp .env.example .env
```

### 2. Edit `.env` with your values

```bash
# Minimum required changes:
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_secure_password
GRAFANA_ADMIN_PASSWORD=your_secure_password

# For live MT5 trading (Windows only):
MT5__MOCK_MODE=false
MT5__LOGIN=your_mt5_account_number
MT5__PASSWORD=your_mt5_password
MT5__SERVER=your_broker_server
```

All settings use the `__` double-underscore delimiter for nested values:

| Variable | Default | Description |
|---|---|---|
| `ENV` | `development` | `development` / `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |
| `LOG_FORMAT` | `json` | `json` (prod) / `console` (dev) |
| `MT5__MOCK_MODE` | `true` | `false` on Windows with real MT5 |
| `MT5__LOGIN` | `0` | MT5 account number |
| `MT5__SERVER` | — | Broker server name |
| `DB__URL` | local | PostgreSQL asyncpg connection URL |
| `REDIS_URL` | local | Redis connection URL |
| `RISK__RISK_PER_TRADE_PCT` | `0.25` | Risk per trade (%) |
| `RISK__DAILY_DD_LIMIT_PCT` | `2.0` | Daily drawdown kill limit (%) |
| `RISK__WEEKLY_DD_LIMIT_PCT` | `5.0` | Weekly drawdown kill limit (%) |
| `RISK__MAX_CONSECUTIVE_LOSSES` | `5` | Consecutive losses before halt |
| `RISK__MAX_LATENCY_MS` | `150.0` | Order latency kill threshold (ms) |
| `RISK__MAX_SPREAD_XAUUSD` | `3.0` | Max spread in points |
| `RISK__MAX_SPREAD_NAS100` | `5.0` | Max spread in points |
| `RISK__MAX_SPREAD_EURUSD` | `1.5` | Max spread in points |

> **Never commit `.env` to git.** It is listed in `.gitignore`.

---

## Infrastructure Setup

All infrastructure runs in Docker. The stack includes PostgreSQL, Redis, Prometheus, and Grafana.

### Start all services

```bash
make up
```

This runs `docker compose -f docker/docker-compose.yml up -d`. Wait ~15 seconds for Postgres to fully initialize.

### Check service health

```bash
docker compose -f docker/docker-compose.yml ps
```

All services should show `healthy` or `running`.

### Service ports

| Service | Port | Credentials |
|---|---|---|
| PostgreSQL | `5432` | `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env` |
| Redis | `6379` | `REDIS_PASSWORD` from `.env` |
| Prometheus | `9090` | No auth |
| Grafana | `3000` | `admin` / `GRAFANA_ADMIN_PASSWORD` from `.env` |
| Dashboard API | `8000` | No auth |

### Stop all services

```bash
make down
```

---

## Database Initialization

Run after the first `make up` to apply the schema:

```bash
python scripts/init_db.py
```

This runs Alembic migrations (`upgrade head`) and verifies the connection. The initial schema is also bootstrapped automatically by the Postgres container on first start via `docker/postgres/init.sql`.

To run migrations manually:

```bash
make migrate
```

---

## Running the Bot

### Development mode (mock MT5, console logging)

```bash
python -m bot_scalp_x.orchestrator
```

Or via the installed entry point:

```bash
bot-scalp-x
```

The bot will:
1. Connect to the MT5 mock gateway
2. Restore kill switch and drawdown state from the database
3. Start tick streams for all configured symbols (default: XAUUSD, NAS100, EURUSD)
4. Run the full pipeline: ticks → features → regime → signals → risk → execution

### View logs

```bash
# Docker app container (if running inside Docker):
make logs

# Or direct console output when running locally — structlog JSON by default.
# Switch to human-readable with:
LOG_FORMAT=console python -m bot_scalp_x.orchestrator
```

### Stop the bot

Send `SIGTERM` or `SIGINT` (Ctrl+C). The bot performs a graceful shutdown: cancels all async tasks, closes the DB pool, and flushes Redis connections.

---

## Dashboard

The FastAPI dashboard exposes a REST API and a Prometheus metrics endpoint.

### Start the dashboard

```bash
uvicorn dashboard.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/readiness` | Readiness (Postgres + Redis) |
| `GET` | `/trades` | Open trades (optional `?symbol=XAUUSD`) |
| `GET` | `/trades/{id}` | Single trade by ID |
| `GET` | `/risk/status` | Kill switch + DD % + consecutive losses |
| `GET` | `/signals/recent` | Last 50 signals (`?symbol=XAUUSD&limit=50`) |
| `GET` | `/metrics` | Prometheus metrics scrape endpoint |

### Grafana

Open [http://localhost:3000](http://localhost:3000) and log in with `admin` / your `GRAFANA_ADMIN_PASSWORD`.

Dashboards are auto-provisioned from `docker/grafana/dashboards/`:
- **Trading Overview** — signals per hour, trade count, win rate
- **Risk Monitor** — daily/weekly DD%, kill switch status, consecutive losses
- **Execution Quality** — order latency histogram, slippage distribution

---

## Training the Regime Model

The regime classifier uses XGBoost to label market conditions as TREND, RANGE, HIGH_VOL, or LOW_VOL. A heuristic fallback runs when no trained model exists.

### Step 1: Obtain tick data

Place a parquet file with columns `symbol`, `ts`, `bid`, `ask`, `volume` in `datasets/raw/`:

```
datasets/raw/xauusd_ticks.parquet
```

Minimum recommended: **6 months** of tick data per symbol.

Or export from your live PostgreSQL after collecting ticks:

```bash
python scripts/export_ticks.py \
  --symbol XAUUSD \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --output datasets/raw/xauusd_ticks.parquet
```

### Step 2: Train the model

```bash
python scripts/train_regime_model.py \
  --symbol XAUUSD \
  --data datasets/raw/xauusd_ticks.parquet \
  --n-estimators 200 \
  --max-depth 6
```

Repeat for NAS100 and EURUSD. Trained models are saved to `src/bot_scalp_x/regime/models/`.

### Cross-validation output

```
regime_cv_accuracy  mean=0.7823  std=0.0312
regime_model_saved  symbol=XAUUSD
```

Accuracy > 70% on cross-validation is acceptable. Below 60% — collect more data or adjust window size in `regime/trainer.py`.

---

## Backtesting

The backtester replays ticks event-by-event with no lookahead bias. All signal and risk logic runs exactly as it does live.

### Run a single backtest

```bash
python tests/backtests/run_backtest.py \
  --symbol XAUUSD \
  --data datasets/raw/xauusd_ticks.parquet \
  --equity 10000
```

**Pass criteria:**

| Metric | Required |
|---|---|
| Profit Factor | > 1.5 |
| Sharpe Ratio | > 1.5 (annualized) |
| Max Drawdown | < 10% |
| Expectancy | > 0 (positive per-trade) |

The script exits with code `1` if any metric fails — use this in CI.

**Example output:**

```json
{
  "total_trades": 312,
  "profit_factor": 1.73,
  "sharpe_ratio": 1.91,
  "max_drawdown_pct": 6.84,
  "expectancy": 4.21,
  "win_rate": 0.532,
  "passes": true
}
```

### Walk-forward test

Tests the strategy across rolling train/test windows to verify robustness over time:

```bash
python tests/backtests/walk_forward.py \
  --symbol XAUUSD \
  --data datasets/raw/xauusd_ticks.parquet
```

Default: 3-month train window, 1-month test window, rolling forward. Reports per-window results and overall pass rate.

---

## Sandbox Sanity Suite

The sanity suite runs 10 targeted checks against the live system before any production promotion. Each check is independent — failures do not cascade.

### Run the suite

```bash
python scripts/run_sandbox.py
```

Or via Make:

```bash
make run-sandbox
```

### Checks performed

| # | Check | What it verifies |
|---|---|---|
| 1 | `mt5_connection` | Gateway connects, returns valid account info |
| 2 | `order_placement` | Market order placed, ticket number returned |
| 3 | `order_cancel` | Order placed then cancelled, no longer in positions |
| 4 | `sl_tp_verification` | SL and TP prices set correctly on placed order |
| 5 | `spread_filter` | Spread > threshold triggers kill switch rejection |
| 6 | `kill_switch` | DD breach activates kill switch, `is_active()` returns True |
| 7 | `db_write` | Database connection verified (SELECT 1) |
| 8 | `telemetry_write` | Prometheus metric emitted and appears in registry |
| 9 | `restart_recovery` | Kill switch state restored from DB snapshot on cold start |
| 10 | `duplicate_prevention` | Second identical order blocked by idempotency key |

### Output

Results are written to `sanity_report.json`:

```json
{
  "timestamp": "2026-05-24T04:11:50Z",
  "all_passed": true,
  "total": 10,
  "passed": 10,
  "failed": 0,
  "checks": [
    { "name": "mt5_connection", "passed": true, "details": "Connected. Login=99999, Equity=10000.0", "elapsed_ms": 40.8 },
    ...
  ]
}
```

---

## Auto-Fix Loop

If the sanity suite has failures, the auto-fix loop attempts to diagnose and resolve them automatically.

### Run the fix loop

```bash
python tests/sandbox/auto_fix/fix_loop.py
```

**Behaviour:**
1. Runs the full sanity suite
2. If any check fails, classifies the failure (connection / config / schema)
3. Applies the appropriate fixer
4. Re-runs the suite
5. Repeats up to **10 iterations**

**Exit codes:**
- `0` — All checks GREEN
- `1` — Max iterations reached without full pass (manual intervention required)

**Fix strategies:**

| Strategy | Trigger | Action |
|---|---|---|
| `connection` | MT5/DB connection refused | Wait 1s, retry |
| `config` | Kill switch / spread / telemetry failures | Validate config, no-op |
| `schema` | Column not found, schema mismatch | Run `alembic upgrade head` |

---

## Merge Gate

The merge gate is the final quality gate before promoting code to `main`. It orchestrates all test suites in sequence and auto-tags a release on full pass.

### Run the merge gate

```bash
make merge-gate
# or:
python tests/merge_gate/run_gate.py
```

**Sequence:**
1. Unit tests (`tests/unit/`)
2. Integration tests (`tests/integration/`)
3. Sandbox sanity + auto-fix loop (`tests/sandbox/`)

**On full GREEN:**
- Tags the commit: `release-v0.1.YYYYMMDDHHMM`
- Logs `merge_gate_passed`

**On any failure:**
- Exits with code `1`
- Logs which step failed

> The merge gate must pass on the `staging` branch before any PR to `main` is created.

---

## Branch Strategy

```
main          ← production-tagged releases only (release-vX.X.X)
  └── staging ← pre-production; merge gate must pass before PR to main
        └── develop ← integration branch; all feature branches merge here
              ├── feature/phase-0-infrastructure
              ├── feature/phase-1-data-pipeline
              ├── feature/...
              └── hotfix/* ← branches from main, merges to main AND develop
```

**Workflow:**

```bash
# 1. Create a feature branch from develop
git checkout develop
git checkout -b feature/my-improvement

# 2. Make changes, commit
git add ...
git commit -m "feat: description"

# 3. Push and open PR to develop
git push -u origin feature/my-improvement

# 4. After PR merged to develop, promote to staging
git checkout staging
git merge develop
git push origin staging

# 5. Run staging sanity + fix loop
python scripts/run_sandbox.py
python tests/sandbox/auto_fix/fix_loop.py

# 6. Run merge gate
make merge-gate

# 7. If GREEN, open PR from staging → main
```

**Rules:**
- No direct commits to `main` or `staging`
- Every commit to `main` must have a `release-vX.X.X` tag
- Hotfixes branch from `main` and merge to both `main` and `develop`

---

## Live Rollout Plan

### Stage 1 — Paper Trading (weeks 1–6)

Run the bot with `MT5__MOCK_MODE=true` (or on a demo MT5 account) and monitor all metrics.

**Go/no-go criteria for Stage 2:**
- Sanity suite: 10/10 GREEN every day for 2 weeks
- Simulated Sharpe > 1.5 over 6 weeks
- Max drawdown < 5% in simulation
- No kill switch triggers from latency or spread

### Stage 2 — Live Capital ($500–$1,000)

```bash
# Switch to live MT5
MT5__MOCK_MODE=false
MT5__LOGIN=your_live_account
MT5__SERVER=your_broker
```

Monitor Grafana dashboards daily. Keep kill switch limits tight: daily DD 1%, weekly DD 3%.

**Go/no-go criteria for Stage 3:**
- 3 consecutive profitable months
- No unexpected kill switch triggers
- Slippage within expected range (< 1 ATR on average)

### Stage 3 — Scale

Gradually increase position size as confidence grows. Re-run walk-forward tests quarterly with updated data. Retrain regime models every 3 months.

---

## Monitoring & Alerts

### Prometheus metrics

All metrics are exposed at `http://localhost:8001/metrics` (bot) and `http://localhost:8000/metrics` (dashboard).

| Metric | Type | Labels |
|---|---|---|
| `order_latency_ms` | Histogram | `symbol`, `order_type` |
| `orders_total` | Counter | `symbol`, `direction`, `status` |
| `slippage_pts` | Histogram | `symbol` |
| `daily_drawdown_pct` | Gauge | `date` |
| `weekly_drawdown_pct` | Gauge | `week` |
| `consecutive_losses` | Gauge | — |
| `kill_switch_active` | Gauge | — (0 or 1) |
| `signals_evaluated_total` | Counter | `symbol`, `result` |
| `ticks_ingested_total` | Counter | `symbol` |
| `feature_compute_ms` | Histogram | `symbol` |
| `spread_pts` | Gauge | `symbol` |

### Recommended Grafana alert rules

| Alert | Condition | Severity |
|---|---|---|
| Kill switch active | `kill_switch_active == 1` | Critical |
| Daily DD approaching | `daily_drawdown_pct > 1.5` | Warning |
| High latency | `order_latency_ms p95 > 120ms` | Warning |
| No ticks received | `rate(ticks_ingested_total[5m]) == 0` | Critical |
| Consecutive losses | `consecutive_losses >= 4` | Warning |

---

## Risk Parameters Reference

All parameters are in `.env` and validated by Pydantic on startup.

| Parameter | Default | Description |
|---|---|---|
| `RISK__RISK_PER_TRADE_PCT` | `0.25` | % of equity risked per trade |
| `RISK__DAILY_DD_LIMIT_PCT` | `2.0` | Daily drawdown limit; triggers kill switch |
| `RISK__WEEKLY_DD_LIMIT_PCT` | `5.0` | Weekly drawdown limit; triggers kill switch |
| `RISK__MAX_CONSECUTIVE_LOSSES` | `5` | Halt after N consecutive losses |
| `RISK__MAX_LATENCY_MS` | `150.0` | Kill switch if order round-trip exceeds this |
| `RISK__MAX_SPREAD_XAUUSD` | `3.0` | Max spread (points) before rejecting XAUUSD trade |
| `RISK__MAX_SPREAD_NAS100` | `5.0` | Max spread (points) before rejecting NAS100 trade |
| `RISK__MAX_SPREAD_EURUSD` | `1.5` | Max spread (points) before rejecting EURUSD trade |

**Position sizing formula:**

```
SL distance = ATR(14) × 1.5
Risk amount = equity × (risk_per_trade_pct / 100)
Lot size    = risk_amount / (SL_distance_in_points × contract_size × point_value)
```

TP is placed at `SL distance × 2.0` (2:1 reward-to-risk ratio).

---

## Signal Logic Reference

All three signals must be evaluated concurrently. A `TradeSignal` is only generated when **at least 2 of 3** agree on direction.

### EMA Pullback

**Long:** Price retraces to EMA(9) while EMA(9) > EMA(21), RSI(14) < 70
**Short:** Price retraces to EMA(9) while EMA(9) < EMA(21), RSI(14) > 30

Confidence = `1 - (distance_from_EMA / 0.8_ATR)`

Tune parameters per symbol in `strategy/signal_configs/{symbol}.yaml`.

### VWAP Rejection

**Long:** Price dips within 0.5 ATR of session VWAP, volume spike > 1.5× average, then closes above VWAP
**Short:** Inverse — price rises to VWAP with volume spike, then closes below

Confidence = `(volume_ratio - 1) × 0.5`, capped at 1.0

### Momentum Breakout

**Long:** Momentum(5) crosses above Momentum(20) with sustained direction
**Short:** Momentum(5) crosses below Momentum(20)

Skips TOKYO session for NAS100 (thin institutional volume).

Confidence = `cross_magnitude / recent_volatility × 0.5`

---

## MT5 Gateway Modes

The factory in `src/bot_scalp_x/gateway/factory.py` selects the gateway automatically:

| Condition | Gateway |
|---|---|
| `MT5__MOCK_MODE=true` (default) | `MT5Mock` — async, Linux-compatible, configurable latency and rejection rates |
| `MT5__MOCK_MODE=false` + Windows | `MT5Gateway` — real MetaTrader5 library, sync calls wrapped in `run_in_executor` |

### Configuring the mock for testing edge cases

The mock accepts constructor parameters for simulating adverse conditions:

```python
from bot_scalp_x.gateway.mt5_mock import MT5Mock

# Simulate 5% rejection rate + 10% partial fill rate
gw = MT5Mock(
    simulate_latency_ms=80.0,
    reject_probability=0.05,
    partial_fill_probability=0.10,
    account_equity=10_000.0,
)
```

---

## MQL5 Bridge

For environments where the Python MetaTrader5 library is not available (Linux servers connecting to a remote Windows MT5 instance), a named-pipe bridge is provided.

**File:** `mql5/BotScalpX_Bridge.mq5`

1. Open MetaEditor in MetaTrader 5
2. Open `mql5/BotScalpX_Bridge.mq5`
3. Compile (`F7`)
4. Attach the compiled EA to any chart
5. The EA listens on `\\.\pipe\BotScalpX` for JSON commands

**Command format:**
```json
{"action": "place_order", "symbol": "XAUUSD", "volume": 0.01, "sl": 1980.0, "tp": 1990.0, "direction": "LONG", "idem_key": "uuid"}
```

**Response format:**
```json
{"ticket": 12345, "price": 1985.23, "volume": 0.01, "status": "OK", "retcode": 10009}
```

> The bridge EA is a scaffold. Full named-pipe WinAPI implementation requires the [WinAPI library for MQL5](https://www.mql5.com/en/code/library).

---

## Troubleshooting

### Bot exits immediately with `MT5 connect() returned False`

Mock mode should always connect. If you see this:
- Check `MT5__MOCK_MODE=true` is set in `.env`
- Verify the `bot_scalp_x` package is installed (`pip install -e ".[dev]"`)

### `ModuleNotFoundError: No module named 'bot_scalp_x'`

The package is not installed. Run:
```bash
pip install -e ".[dev]"
```

### `asyncpg: could not connect to server` / database errors

- Confirm Docker services are running: `make up`
- Wait 15 seconds after `make up` for Postgres to finish initializing
- Check `POSTGRES_PASSWORD` in `.env` matches `DB__URL`

### `redis.exceptions.AuthenticationError`

- Confirm `REDIS_PASSWORD` in `.env` matches `REDIS_URL`
- Format: `redis://:YOUR_PASSWORD@localhost:6379/0`

### Kill switch is stuck ACTIVE after restart

The kill switch state is restored from the database on startup (by design — prevents trading after a shutdown triggered by a drawdown breach). To manually reset:

```bash
redis-cli -a YOUR_REDIS_PASSWORD SET risk:kill_switch INACTIVE
```

Then update the drawdown snapshot in Postgres:
```sql
UPDATE drawdown_snapshots
SET kill_switch_active = FALSE
WHERE snapshot_date = CURRENT_DATE;
```

### Sanity check `db_write` always SKIPPED

This check requires `DB__URL` to contain `localhost` or `postgres`. Set the full URL in `.env`:
```
DB__URL=postgresql+asyncpg://bot:password@localhost:5432/bot_scalp_x
```

### Regime model not found warning

This is not an error. The bot falls back to a heuristic regime classifier. To suppress the warning, train a model:
```bash
python scripts/train_regime_model.py --symbol XAUUSD --data datasets/raw/xauusd_ticks.parquet
```

### `pytest` collects no tests

Ensure you're running from the project root:
```bash
cd /path/to/Trade-bot
python -m pytest tests/unit -v
```

### `make` command not found

Install `make`:
- Ubuntu/Debian: `sudo apt-get install make`
- macOS: `xcode-select --install`
- Windows: use `mingw32-make` or run commands from the `Makefile` directly

---

## Quick Reference

```bash
# Setup
cp .env.example .env && nano .env
pip install -e ".[dev]"
make up
python scripts/init_db.py

# Develop
make test-unit                          # Fast unit tests (no Docker needed)
make test                               # Unit + integration tests
make lint                               # ruff + mypy

# Run bot
python -m bot_scalp_x.orchestrator     # Start bot (mock mode)

# Dashboard
uvicorn dashboard.main:app --reload    # Start API dashboard

# Train
python scripts/train_regime_model.py --symbol XAUUSD --data datasets/raw/xauusd_ticks.parquet

# Backtest
python tests/backtests/run_backtest.py --symbol XAUUSD --data datasets/raw/xauusd_ticks.parquet

# Sanity check
make run-sandbox                        # → sanity_report.json

# Auto-fix failures
python tests/sandbox/auto_fix/fix_loop.py

# Merge gate (before staging → main)
make merge-gate
```
