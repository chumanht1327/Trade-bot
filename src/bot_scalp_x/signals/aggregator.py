"""2-of-3 signal voting aggregator. Returns TradeSignal or None."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.signals.base import BaseSignal
from bot_scalp_x.signals.ema_pullback import EMAPullbackSignal
from bot_scalp_x.signals.momentum_breakout import MomentumBreakoutSignal
from bot_scalp_x.signals.schemas import Direction, SignalResult, TradeSignal
from bot_scalp_x.signals.vwap_rejection import VWAPRejectionSignal

log = structlog.get_logger(__name__)


class SignalAggregator:
    def __init__(self, min_votes: int = 2) -> None:
        self.min_votes = min_votes
        self._signals: list[BaseSignal] = [
            EMAPullbackSignal(),
            VWAPRejectionSignal(),
            MomentumBreakoutSignal(),
        ]

    async def evaluate(self, features: FeatureRow, history: list[FeatureRow]) -> TradeSignal | None:
        results: list[SignalResult] = list(
            await asyncio.gather(
                *[s.evaluate(features, history) for s in self._signals]
            )
        )

        long_votes = [r for r in results if r.fired and r.direction == Direction.LONG]
        short_votes = [r for r in results if r.fired and r.direction == Direction.SHORT]

        if len(long_votes) >= self.min_votes:
            votes = long_votes
            direction = Direction.LONG
        elif len(short_votes) >= self.min_votes:
            votes = short_votes
            direction = Direction.SHORT
        else:
            return None

        confidence = sum(r.confidence for r in votes) / len(votes)
        regime = features.regime or "RANGE"

        log.info(
            "signal_generated",
            symbol=features.symbol,
            direction=direction.value,
            votes=len(votes),
            confidence=round(confidence, 4),
            regime=regime,
        )

        return TradeSignal(
            symbol=features.symbol,
            ts=features.ts,
            direction=direction,
            votes=len(votes),
            confidence=confidence,
            signals=tuple(results),
            regime=regime,
        )
