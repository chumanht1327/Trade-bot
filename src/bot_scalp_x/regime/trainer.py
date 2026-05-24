"""Training pipeline: load parquet ticks → engineer features → train XGBoost → serialize."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from bot_scalp_x.regime.classifier import REGIME_CLASSES, RegimeClassifier, _FEATURE_ORDER
from bot_scalp_x.regime.evaluator import label_regime

log = structlog.get_logger(__name__)


def train(symbol: str, parquet_path: Path, n_estimators: int = 200, max_depth: int = 6) -> None:
    """Load tick parquet, label regimes, train XGBoost, save to models/."""
    log.info("regime_training_start", symbol=symbol, data=str(parquet_path))

    df = pd.read_parquet(parquet_path)
    df = df[df["symbol"] == symbol].sort_values("ts").reset_index(drop=True)

    if len(df) < 500:
        raise ValueError(f"Need at least 500 rows to train; got {len(df)}")

    # Label regimes using heuristic over rolling windows
    labels, feature_rows_list = label_regime(df)

    X = np.array([[row.get(f, 0.0) for f in _FEATURE_ORDER] for row in feature_rows_list])
    le = LabelEncoder()
    le.fit(REGIME_CLASSES)
    y = le.transform(labels)

    model = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    log.info("regime_cv_accuracy", symbol=symbol, mean=round(float(scores.mean()), 4), std=round(float(scores.std()), 4))

    model.fit(X, y)

    classifier = RegimeClassifier(symbol)
    classifier.save(model)
    log.info("regime_training_complete", symbol=symbol)
