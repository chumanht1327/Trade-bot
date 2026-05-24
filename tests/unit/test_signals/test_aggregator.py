"""Unit tests for the 2-of-3 signal aggregator."""

import pytest
from datetime import datetime, timezone

from bot_scalp_x.signals.aggregator import SignalAggregator
from bot_scalp_x.signals.schemas import Direction, SignalResult


def make_result(name: str, fired: bool, direction: Direction, confidence: float = 0.7) -> SignalResult:
    return SignalResult(name=name, fired=fired, direction=direction, confidence=confidence)


@pytest.mark.asyncio
class TestAggregator:
    async def _eval(self, results, feature_row, history):
        """Patch aggregator to use fixed results."""
        from unittest.mock import AsyncMock
        agg = SignalAggregator(min_votes=2)
        for i, sig in enumerate(agg._signals):
            sig.evaluate = AsyncMock(return_value=results[i])
        return await agg.evaluate(feature_row, history)

    async def test_two_long_votes_generates_long_signal(self, feature_row_factory):
        row = feature_row_factory()
        results = [
            make_result("EMA_PULLBACK", True, Direction.LONG),
            make_result("VWAP_REJECTION", True, Direction.LONG),
            make_result("MOMENTUM_BREAKOUT", False, Direction.NEUTRAL),
        ]
        signal = await self._eval(results, row, [row])
        assert signal is not None
        assert signal.direction == Direction.LONG
        assert signal.votes == 2

    async def test_two_short_votes_generates_short_signal(self, feature_row_factory):
        row = feature_row_factory()
        results = [
            make_result("EMA_PULLBACK", False, Direction.NEUTRAL),
            make_result("VWAP_REJECTION", True, Direction.SHORT),
            make_result("MOMENTUM_BREAKOUT", True, Direction.SHORT),
        ]
        signal = await self._eval(results, row, [row])
        assert signal is not None
        assert signal.direction == Direction.SHORT

    async def test_one_vote_returns_none(self, feature_row_factory):
        row = feature_row_factory()
        results = [
            make_result("EMA_PULLBACK", True, Direction.LONG),
            make_result("VWAP_REJECTION", False, Direction.NEUTRAL),
            make_result("MOMENTUM_BREAKOUT", False, Direction.NEUTRAL),
        ]
        signal = await self._eval(results, row, [row])
        assert signal is None

    async def test_conflicting_votes_returns_none(self, feature_row_factory):
        row = feature_row_factory()
        results = [
            make_result("EMA_PULLBACK", True, Direction.LONG),
            make_result("VWAP_REJECTION", True, Direction.SHORT),
            make_result("MOMENTUM_BREAKOUT", False, Direction.NEUTRAL),
        ]
        signal = await self._eval(results, row, [row])
        assert signal is None

    async def test_three_votes_generates_high_confidence(self, feature_row_factory):
        row = feature_row_factory()
        results = [
            make_result("EMA_PULLBACK", True, Direction.LONG, 0.9),
            make_result("VWAP_REJECTION", True, Direction.LONG, 0.8),
            make_result("MOMENTUM_BREAKOUT", True, Direction.LONG, 0.7),
        ]
        signal = await self._eval(results, row, [row])
        assert signal is not None
        assert signal.votes == 3
        assert abs(signal.confidence - 0.8) < 0.05  # average of 0.9, 0.8, 0.7
