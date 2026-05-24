"""Regime-specific feature extraction from FeatureRow sequences."""

from __future__ import annotations

import numpy as np

from bot_scalp_x.data.schemas import FeatureRow


def extract_regime_features(rows: list[FeatureRow]) -> dict[str, float]:
    """Extract features used by the regime classifier from a window of FeatureRows."""
    if not rows:
        return {}

    mids = np.array([float(r.tick.mid) for r in rows])
    atrs = np.array([r.atr_14 for r in rows])
    mom5s = np.array([r.momentum_5 for r in rows])
    mom20s = np.array([r.momentum_20 for r in rows])
    spreads = np.array([float(r.tick.spread_pts) for r in rows])
    liqs = np.array([r.liquidity_score for r in rows])

    price_range = float(np.max(mids) - np.min(mids))
    avg_atr = float(np.mean(atrs))

    # Trend strength: ratio of directional movement to total range
    trend_strength = abs(float(mids[-1] - mids[0])) / (price_range + 1e-10)

    # Volatility ratio: recent ATR vs. longer ATR window
    half = len(atrs) // 2
    vol_ratio = float(np.mean(atrs[-half:])) / (float(np.mean(atrs[:half])) + 1e-10) if half > 0 else 1.0

    # Momentum agreement: how consistently momentum 5 and 20 agree on direction
    mom_agreement = float(np.mean(np.sign(mom5s) == np.sign(mom20s)))

    # Price oscillation: normalized std-dev around VWAP
    vwaps = np.array([r.vwap for r in rows])
    vwap_dev = float(np.std(mids - vwaps)) / (avg_atr + 1e-10)

    return {
        "trend_strength": trend_strength,
        "volatility_ratio": vol_ratio,
        "momentum_agreement": mom_agreement,
        "vwap_deviation": vwap_dev,
        "avg_atr": avg_atr,
        "avg_liquidity": float(np.mean(liqs)),
        "avg_spread": float(np.mean(spreads)),
        "price_range_pct": price_range / (float(mids[0]) + 1e-10),
    }
