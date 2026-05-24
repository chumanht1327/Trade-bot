"""XGBoost regime classifier wrapper. Predicts TREND/RANGE/HIGH_VOL/LOW_VOL."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import structlog
from xgboost import XGBClassifier

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.regime.features import extract_regime_features

log = structlog.get_logger(__name__)

REGIME_CLASSES = ["TREND", "RANGE", "HIGH_VOL", "LOW_VOL"]
_MODELS_DIR = Path(__file__).parent / "models"
_FEATURE_ORDER = [
    "trend_strength", "volatility_ratio", "momentum_agreement",
    "vwap_deviation", "avg_atr", "avg_liquidity", "avg_spread", "price_range_pct",
]


class RegimeClassifier:
    def __init__(self, symbol: str, window: int = 100) -> None:
        self.symbol = symbol
        self.window = window
        self._model: XGBClassifier | None = None
        self._load_model()

    def _model_path(self) -> Path:
        return _MODELS_DIR / f"regime_{self.symbol.lower()}.joblib"

    def _load_model(self) -> None:
        path = self._model_path()
        if path.exists():
            self._model = joblib.load(path)
            log.info("regime_model_loaded", symbol=self.symbol)
        else:
            log.warning("regime_model_not_found", symbol=self.symbol, path=str(path))

    def predict(self, rows: list[FeatureRow]) -> tuple[str, float]:
        """Return (regime_label, confidence). Falls back to heuristic if no model."""
        if len(rows) < 10:
            return "RANGE", 0.5

        features = extract_regime_features(rows[-self.window :])
        if not features:
            return "RANGE", 0.5

        if self._model is not None:
            x = np.array([[features.get(f, 0.0) for f in _FEATURE_ORDER]])
            proba = self._model.predict_proba(x)[0]
            idx = int(np.argmax(proba))
            return REGIME_CLASSES[idx], float(proba[idx])

        # Heuristic fallback when no trained model is available
        return self._heuristic_regime(features)

    def _heuristic_regime(self, features: dict[str, float]) -> tuple[str, float]:
        ts = features.get("trend_strength", 0.0)
        vr = features.get("volatility_ratio", 1.0)

        if vr > 1.5:
            return "HIGH_VOL", 0.6
        if vr < 0.7:
            return "LOW_VOL", 0.6
        if ts > 0.6:
            return "TREND", 0.65
        return "RANGE", 0.65

    def save(self, model: XGBClassifier) -> None:
        _MODELS_DIR.mkdir(exist_ok=True)
        joblib.dump(model, self._model_path())
        self._model = model
        log.info("regime_model_saved", symbol=self.symbol)
