"""Regime evaluation utilities: labeling, confusion matrix, transition stats."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bot_scalp_x.regime.features import extract_regime_features

_WINDOW = 100
_STEP = 20


def label_regime(df: pd.DataFrame) -> tuple[list[str], list[dict]]:
    """Heuristic regime labeling over rolling windows for training data generation."""
    labels = []
    feature_dicts = []

    for i in range(_WINDOW, len(df), _STEP):
        window = df.iloc[i - _WINDOW : i]

        mids = (window["bid"] + window["ask"]) / 2
        price_range = float(mids.max() - mids.min())
        trend_strength = abs(float(mids.iloc[-1] - mids.iloc[0])) / (price_range + 1e-10)

        spreads = window["ask"] - window["bid"]
        avg_spread = float(spreads.mean())
        spread_std = float(spreads.std())
        vol_ratio = spread_std / (avg_spread + 1e-10)

        if vol_ratio > 1.2:
            regime = "HIGH_VOL"
        elif vol_ratio < 0.4:
            regime = "LOW_VOL"
        elif trend_strength > 0.55:
            regime = "TREND"
        else:
            regime = "RANGE"

        # Build a pseudo feature dict for training
        vols = window.get("volume", pd.Series([1.0] * len(window)))
        feat = {
            "trend_strength": trend_strength,
            "volatility_ratio": vol_ratio,
            "momentum_agreement": 0.5,
            "vwap_deviation": spread_std,
            "avg_atr": avg_spread * 10,
            "avg_liquidity": 0.5,
            "avg_spread": avg_spread,
            "price_range_pct": price_range / (float(mids.iloc[0]) + 1e-10),
        }
        labels.append(regime)
        feature_dicts.append(feat)

    return labels, feature_dicts


def confusion_summary(y_true: list[str], y_pred: list[str]) -> dict:
    classes = sorted(set(y_true + y_pred))
    matrix: dict[str, dict[str, int]] = {c: {d: 0 for d in classes} for c in classes}
    for t, p in zip(y_true, y_pred):
        matrix[t][p] += 1
    return matrix
