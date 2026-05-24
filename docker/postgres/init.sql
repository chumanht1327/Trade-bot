-- BOT-SCALP-X Initial Schema
-- Executed once on first postgres container start.
-- Alembic manages subsequent migrations.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ── Enums ─────────────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE trade_direction AS ENUM ('LONG', 'SHORT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE trade_status AS ENUM ('PENDING','OPEN','PARTIAL','CLOSED','CANCELLED','REJECTED','FAILED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE regime_type AS ENUM ('TREND','RANGE','HIGH_VOL','LOW_VOL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE session_type AS ENUM ('LONDON','NY','TOKYO','OVERLAP','OFF');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE exec_event_type AS ENUM ('ORDER_SENT','FILL_RECEIVED','RETRY','REJECTED','CANCELLED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Ticks (partitioned by month) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ticks (
    id          BIGSERIAL,
    symbol      VARCHAR(10)   NOT NULL,
    ts          TIMESTAMPTZ   NOT NULL,
    bid         NUMERIC(12,5) NOT NULL,
    ask         NUMERIC(12,5) NOT NULL,
    spread_pts  NUMERIC(8,3),
    volume      NUMERIC(16,4),
    session     session_type,
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

-- Seed partitions for current + next 3 months (APScheduler creates future ones)
CREATE TABLE IF NOT EXISTS ticks_2026_05 PARTITION OF ticks
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS ticks_2026_06 PARTITION OF ticks
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS ticks_2026_07 PARTITION OF ticks
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS ticks_2026_08 PARTITION OF ticks
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks (symbol, ts DESC);

-- ── Feature Rows ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feature_rows (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              VARCHAR(10)    NOT NULL,
    ts                  TIMESTAMPTZ    NOT NULL,
    atr_14              NUMERIC(12,5),
    vwap                NUMERIC(12,5),
    momentum_5          NUMERIC(12,5),
    momentum_20         NUMERIC(12,5),
    liquidity_score     NUMERIC(6,4),
    regime              regime_type,
    regime_confidence   NUMERIC(5,4),
    created_at          TIMESTAMPTZ    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feature_rows_symbol_ts ON feature_rows (symbol, ts DESC);

-- ── Signals ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(10)    NOT NULL,
    ts              TIMESTAMPTZ    NOT NULL,
    ema_pullback    BOOLEAN,
    vwap_rejection  BOOLEAN,
    momentum_break  BOOLEAN,
    votes           SMALLINT,
    direction       trade_direction,
    confidence      NUMERIC(5,4),
    regime          regime_type,
    acted_on        BOOLEAN        DEFAULT FALSE,
    created_at      TIMESTAMPTZ    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_ts ON signals (symbol, ts DESC);

-- ── Trades ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id              BIGSERIAL PRIMARY KEY,
    external_id     VARCHAR(50)    UNIQUE,
    symbol          VARCHAR(10)    NOT NULL,
    signal_id       BIGINT         REFERENCES signals(id),
    direction       trade_direction NOT NULL,
    entry_price     NUMERIC(12,5),
    sl_price        NUMERIC(12,5),
    tp_price        NUMERIC(12,5),
    lot_size        NUMERIC(10,4),
    risk_pct        NUMERIC(6,4),
    status          trade_status   NOT NULL DEFAULT 'PENDING',
    open_ts         TIMESTAMPTZ,
    close_ts        TIMESTAMPTZ,
    close_price     NUMERIC(12,5),
    realized_pnl    NUMERIC(12,2),
    slippage_pts    NUMERIC(8,3),
    fills_json      JSONB,
    created_at      TIMESTAMPTZ    DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON trades (symbol, status);
CREATE INDEX IF NOT EXISTS idx_trades_open_ts       ON trades (open_ts DESC);

-- ── Drawdown Snapshots ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drawdown_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    snapshot_date       DATE          NOT NULL,
    snapshot_week       DATE          NOT NULL,
    daily_dd_pct        NUMERIC(8,4),
    weekly_dd_pct       NUMERIC(8,4),
    equity_start        NUMERIC(16,2),
    equity_current      NUMERIC(16,2),
    consecutive_losses  SMALLINT      DEFAULT 0,
    kill_switch_active  BOOLEAN       DEFAULT FALSE,
    created_at          TIMESTAMPTZ   DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dd_snapshots_date ON drawdown_snapshots (snapshot_date);

-- ── Execution Events ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS execution_events (
    id          BIGSERIAL PRIMARY KEY,
    trade_id    BIGINT         REFERENCES trades(id),
    event_type  exec_event_type NOT NULL,
    ts          TIMESTAMPTZ    NOT NULL,
    latency_ms  NUMERIC(10,3),
    payload     JSONB,
    created_at  TIMESTAMPTZ    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_exec_events_trade_id ON execution_events (trade_id);
CREATE INDEX IF NOT EXISTS idx_exec_events_ts       ON execution_events (ts DESC);

-- ── Updated-at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trades_updated_at ON trades;
CREATE TRIGGER trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
