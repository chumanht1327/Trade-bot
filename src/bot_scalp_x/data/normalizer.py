"""Z-score normalization for ML model inputs. Fitted per symbol on training data."""

from __future__ import annotations

import numpy as np


class ZScoreNormalizer:
    def __init__(self) -> None:
        self._mean: dict[str, float] = {}
        self._std: dict[str, float] = {}

    def fit(self, data: dict[str, list[float]]) -> None:
        for col, values in data.items():
            arr = np.array(values, dtype=float)
            self._mean[col] = float(arr.mean())
            self._std[col] = float(arr.std()) or 1.0

    def transform(self, data: dict[str, float]) -> dict[str, float]:
        return {
            col: (val - self._mean.get(col, 0.0)) / (self._std.get(col, 1.0))
            for col, val in data.items()
        }

    def fit_transform(self, data: dict[str, list[float]]) -> dict[str, list[float]]:
        self.fit(data)
        result: dict[str, list[float]] = {}
        for col, values in data.items():
            result[col] = [self.transform({col: v})[col] for v in values]
        return result
