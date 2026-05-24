"""Momentum Breakout signal: Momentum(5) crosses Momentum(20) with sustained direction."""

from __future__ import annotations

import numpy as np

from bot_scalp_x.data.schemas import FeatureRow, Session
from bot_scalp_x.signals.base import BaseSignal
from bot_scalp_x.signals.schemas import Direction, SignalResult

# Sessions unsuitable for NAS100 breakout (low institutional volume)
_NAS100_BLOCKED_SESSIONS = {Session.TOKYO, Session.OFF}


class MomentumBreakoutSignal(BaseSignal):
    """
    Fires when Momentum(5) crosses above/below Momentum(20).
    Requires the cross to be sustained (confirmed by recent history direction).
    Skips TOKYO session for NAS100 (thin liquidity).
    """

    def __init__(self, confirmation_bars: int = 3) -> None:
        self.confirmation_bars = confirmation_bars

    async def evaluate(self, features: FeatureRow, history: list[FeatureRow]) -> SignalResult:
        min_bars = 25 + self.confirmation_bars
        if len(history) < min_bars:
            return SignalResult("MOMENTUM_BREAKOUT", False, Direction.NEUTRAL, 0.0)

        if features.symbol == "NAS100" and features.session in _NAS100_BLOCKED_SESSIONS:
            return SignalResult("MOMENTUM_BREAKOUT", False, Direction.NEUTRAL, 0.0,
                                {"blocked_session": features.session.value})

        recent = history[-min_bars:]
        mom5 = np.array([r.momentum_5 for r in recent])
        mom20 = np.array([r.momentum_20 for r in recent])

        # Detect cross in the most recent confirmation_bars
        cross_window_5 = mom5[-self.confirmation_bars - 1 :]
        cross_window_20 = mom20[-self.confirmation_bars - 1 :]

        prev_diff = cross_window_5[0] - cross_window_20[0]
        curr_diff = cross_window_5[-1] - cross_window_20[-1]

        bullish_cross = prev_diff <= 0 < curr_diff
        bearish_cross = prev_diff >= 0 > curr_diff

        if not (bullish_cross or bearish_cross):
            return SignalResult("MOMENTUM_BREAKOUT", False, Direction.NEUTRAL, 0.0)

        # Normalize confidence by recent volatility
        mom_magnitude = abs(curr_diff)
        recent_vol = float(np.std(mom5)) + 1e-10
        confidence = min(1.0, mom_magnitude / recent_vol * 0.5)

        direction = Direction.LONG if bullish_cross else Direction.SHORT
        return SignalResult(
            "MOMENTUM_BREAKOUT", True, direction, confidence,
            {"mom5": float(mom5[-1]), "mom20": float(mom20[-1]),
             "cross_magnitude": mom_magnitude, "session": features.session.value},
        )
