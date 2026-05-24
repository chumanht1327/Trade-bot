"""Unit tests for the feature engine (pure computation, no I/O)."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from bot_scalp_x.data.feature_engine import FeatureEngine, _anchored_vwap, _liquidity_score
from bot_scalp_x.data.schemas import Tick


def make_tick(bid: float, ask: float, vol: float = 1.0, symbol: str = "XAUUSD") -> Tick:
    return Tick(
        symbol=symbol,
        ts=datetime.now(tz=timezone.utc),
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        volume=vol,
    )


def make_engine_with_ticks(n: int, base: float = 1985.0, step: float = 0.02) -> tuple[FeatureEngine, list]:
    """Return an engine and the list of feature rows after feeding n ticks."""
    engine = FeatureEngine("XAUUSD", atr_period=14)
    ticks = [make_tick(base + i * step, base + 0.5 + i * step, vol=float(i + 1)) for i in range(n)]
    rows = [engine.update(t) for t in ticks]
    return engine, rows


def test_atr_positive_after_warmup():
    """ATR must be a small positive number once the engine has enough history."""
    _, rows = make_engine_with_ticks(30)
    populated = [r for r in rows if r is not None]
    assert populated, "Should produce feature rows after warm-up"
    assert populated[-1].atr_14 > 0, f"ATR should be positive, got {populated[-1].atr_14}"


def test_momentum_positive_for_uptrend():
    """Consistent upward prices should yield positive 5-period momentum."""
    engine = FeatureEngine("XAUUSD", atr_period=14)
    # Feed 35 ticks with steadily rising prices
    ticks = [make_tick(1000.0 + i * 1.0, 1000.5 + i * 1.0, vol=1.0) for i in range(35)]
    rows = [engine.update(t) for t in ticks]
    populated = [r for r in rows if r is not None]
    assert populated, "Engine must produce rows after warm-up"
    assert populated[-1].momentum_5 > 0, f"Expected positive momentum, got {populated[-1].momentum_5}"


def test_momentum_negative_for_downtrend():
    """Consistent downward prices should yield negative 5-period momentum."""
    engine = FeatureEngine("XAUUSD", atr_period=14)
    ticks = [make_tick(1000.0 - i * 0.5, 1000.5 - i * 0.5, vol=1.0) for i in range(35)]
    rows = [engine.update(t) for t in ticks]
    populated = [r for r in rows if r is not None]
    assert populated
    assert populated[-1].momentum_5 < 0, f"Expected negative momentum, got {populated[-1].momentum_5}"


def test_feature_engine_returns_none_until_warm():
    engine = FeatureEngine("XAUUSD", atr_period=14)
    ticks = [make_tick(1985.0 + i * 0.01, 1985.5 + i * 0.01) for i in range(15)]
    results = [engine.update(t) for t in ticks]
    assert all(r is None for r in results), "Engine should return None before warm-up"


def test_feature_engine_produces_row_after_warmup():
    _, rows = make_engine_with_ticks(30)
    populated = [r for r in rows if r is not None]
    assert len(populated) > 0, "Engine should produce rows after warm-up"
    row = populated[-1]
    assert row.symbol == "XAUUSD"
    assert row.atr_14 > 0
    assert 0.0 <= row.liquidity_score <= 1.0


def test_feature_engine_vwap_reasonable():
    engine = FeatureEngine("XAUUSD", atr_period=14)
    mid = 2000.0
    ticks = [make_tick(mid - 0.5, mid + 0.5, vol=1.0) for _ in range(30)]
    rows = [engine.update(t) for t in ticks]
    populated = [r for r in rows if r is not None]
    assert populated, "Should produce feature rows"
    assert abs(populated[-1].vwap - mid) < 5.0


def test_anchored_vwap_zero_volume():
    prices = np.array([100.0, 101.0, 102.0])
    volumes = np.array([0.0, 0.0, 0.0])
    vwap = _anchored_vwap(prices, volumes)
    assert vwap == pytest.approx(102.0)


def test_liquidity_score_bounds():
    score = _liquidity_score(Decimal("0.3"), [0.3, 0.4, 0.5], 5.0, [1.0, 3.0, 5.0])
    assert 0.0 <= score <= 1.0


def test_liquidity_score_empty_history():
    assert _liquidity_score(Decimal("0.5"), [], 1.0, []) == 0.5
