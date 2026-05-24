"""EMA Pullback signal: price pulls back to fast EMA while trend is intact."""

from __future__ import annotations

import numpy as np
import talib  # type: ignore[import]

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.signals.base import BaseSignal
from bot_scalp_x.signals.schemas import Direction, SignalResult


class EMAPullbackSignal(BaseSignal):
    """
    Long: price pulls back to EMA(fast) while EMA(fast) > EMA(slow) and RSI not overbought.
    Short: inverse conditions.
    """

    def __init__(self, ema_fast: int = 9, ema_slow: int = 21, rsi_period: int = 14) -> None:
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period

    async def evaluate(self, features: FeatureRow, history: list[FeatureRow]) -> SignalResult:
        min_bars = self.ema_slow + 5
        if len(history) < min_bars:
            return SignalResult("EMA_PULLBACK", False, Direction.NEUTRAL, 0.0)

        mids = np.array([float(r.tick.mid) for r in history], dtype=np.float64)

        fast_arr = talib.EMA(mids, timeperiod=self.ema_fast)
        slow_arr = talib.EMA(mids, timeperiod=self.ema_slow)
        rsi_arr = talib.RSI(mids, timeperiod=self.rsi_period)

        fast_val = float(fast_arr[-1])
        slow_val = float(slow_arr[-1])
        rsi = float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50.0

        if np.isnan(fast_val) or np.isnan(slow_val):
            return SignalResult("EMA_PULLBACK", False, Direction.NEUTRAL, 0.0)

        price = float(features.tick.mid)
        atr = features.atr_14

        distance_from_ema = abs(price - fast_val) / (atr + 1e-10)
        at_ema = distance_from_ema < 0.8  # within 0.8 ATR of fast EMA

        if fast_val > slow_val and at_ema and price > fast_val * 0.9995 and rsi < 70:
            # Bullish trend + price near EMA from above + not overbought
            confidence = max(0.0, min(1.0, 1.0 - distance_from_ema / 0.8))
            return SignalResult(
                "EMA_PULLBACK",
                True,
                Direction.LONG,
                confidence,
                {"rsi": rsi, "distance_atr": distance_from_ema, "ema_fast": fast_val, "ema_slow": slow_val},
            )
        if fast_val < slow_val and at_ema and price < fast_val * 1.0005 and rsi > 30:
            # Bearish trend + price near EMA from below + not oversold
            confidence = max(0.0, min(1.0, 1.0 - distance_from_ema / 0.8))
            return SignalResult(
                "EMA_PULLBACK",
                True,
                Direction.SHORT,
                confidence,
                {"rsi": rsi, "distance_atr": distance_from_ema, "ema_fast": fast_val, "ema_slow": slow_val},
            )

        return SignalResult(
            "EMA_PULLBACK",
            False,
            Direction.NEUTRAL,
            0.0,
            {"rsi": rsi, "distance_atr": distance_from_ema},
        )
