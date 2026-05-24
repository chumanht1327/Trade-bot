"""Abstract base class for all signal implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.signals.schemas import SignalResult


class BaseSignal(ABC):
    @abstractmethod
    async def evaluate(self, features: FeatureRow, history: list[FeatureRow]) -> SignalResult:
        """
        Evaluate the signal against the latest feature row and recent history.

        Args:
            features: Most recent feature row (current tick).
            history: Recent feature rows ordered oldest-first (including current).
        """
        ...
