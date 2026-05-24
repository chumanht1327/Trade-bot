"""Unit tests for the feature engine (pure computation, no I/O)."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from bot_scalp_x.data.feature_engine import FeatureEngine, _wilder_atr, _momentum
from bot_scalp_x.data.schemas import Tick


def make_tick(bid: float, ask: float, vol: float = 1.0, symbol: str = "XAUUSD") -> Tick:
    return Tick(
        symbol=symbol,
        ts=datetime.now(tz=timezone.utc),
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        volume=vol,
    )


def test_wilder_atr_basic():
    highs = [10.0, 11.0, 12.0, 11.5, 10.5, 11.0, 12.5, 11.0, 10.0, 11.5, 12.0, 11.0, 10.5, 11.0, 12.0]
    lows  = [9.0,  10.0, 11.0, 10.5, 9.5,  10.0, 11.5, 10.0, 9.0,  10.5, 11.0, 10.0, 9.5,  10.0, 11.0]
    closes= [9.5,  10.5, 11.5, 11.0, 10.0, 10.5, 12.0, 10.5, 9.5,  11.0, 11.5, 10.5, 10.0, 10.5, 11.5]
    import numpy as np
    atr = _wilder_atr(np.array(highs), np.array(lows), np.array(closes), 14)
    assert 0.5 < atr < 3.0, f"ATR out of expected range: {atr}"


def test_momentum_direction():
    import numpy as np
    # Upward trending prices → positive momentum
    prices = np.array([100.0 + i * 0.1 for i in range(30)])
    mom5 = _momentum(prices, 5)
    assert mom5 > 0, "Expected positive momentum for uptrend"

    # Downward prices → negative momentum
    prices_down = np.array([100.0 - i * 0.1 for i in range(30)])
    mom5_down = _momentum(prices_down, 5)
    assert mom5_down < 0


def test_momentum_insufficient_data():
    import numpy as np
    prices = np.array([1.0, 2.0, 3.0])
    assert _momentum(prices, 5) == 0.0


def test_feature_engine_returns_none_until_warm():
    engine = FeatureEngine("XAUUSD", atr_period=14)
    ticks = [make_tick(1985.0 + i * 0.01, 1985.5 + i * 0.01) for i in range(15)]
    results = [engine.update(t) for t in ticks]
    assert all(r is None for r in results), "Engine should return None before warm-up"


def test_feature_engine_produces_row_after_warmup():
    engine = FeatureEngine("XAUUSD", atr_period=14)
    ticks = [make_tick(1985.0 + i * 0.02, 1985.5 + i * 0.02, vol=float(i + 1)) for i in range(30)]
    rows = [engine.update(t) for t in ticks]
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
    # VWAP should be near the constant mid price
    assert abs(populated[-1].vwap - mid) < 5.0
