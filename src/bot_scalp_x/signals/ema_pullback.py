"""EMA Pullback signal: price pulls back to fast EMA while trend is intact."""

from __future__ import annotations

import numpy as np

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.signals.base import BaseSignal
from bot_scalp_x.signals.schemas import Direction, SignalResult


def _ema(prices: np.ndarray, period: int) -> np.ndarray:
    result = np.empty_like(prices)
    if len(prices) == 0:
        return result
    result[0] = prices[0]
    k = 2.0 / (period + 1)
    for i in range(1, len(prices)):
        result[i] = prices[i] * k + result[i - 1] * (1 - k)
    return result


def _rsi(prices: np.ndarray, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-(period + 1) :])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


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

        mids = np.array([float(r.tick.mid) for r in history])
        fast = _ema(mids, self.ema_fast)
        slow = _ema(mids, self.ema_slow)
        rsi = _rsi(mids, self.rsi_period)

        price = float(features.tick.mid)
        atr = features.atr_14
        fast_val = float(fast[-1])
        slow_val = float(slow[-1])

        distance_from_ema = abs(price - fast_val) / (atr + 1e-10)
        at_ema = distance_from_ema < 0.8  # within 0.8 ATR of fast EMA

        if fast_val > slow_val and at_ema and price > fast_val * 0.9995 and rsi < 70:
            # Bullish trend + price near EMA from above + not overbought
            confidence = max(0.0, min(1.0, 1.0 - distance_from_ema / 0.8))
            return SignalResult(
                "EMA_PULLBACK", True, Direction.LONG, confidence,
                {"rsi": rsi, "distance_atr": distance_from_ema, "ema_fast": fast_val, "ema_slow": slow_val},
            )
        if fast_val < slow_val and at_ema and price < fast_val * 1.0005 and rsi > 30:
            # Bearish trend + price near EMA from below + not oversold
            confidence = max(0.0, min(1.0, 1.0 - distance_from_ema / 0.8))
            return SignalResult(
                "EMA_PULLBACK", True, Direction.SHORT, confidence,
                {"rsi": rsi, "distance_atr": distance_from_ema, "ema_fast": fast_val, "ema_slow": slow_val},
            )

        return SignalResult("EMA_PULLBACK", False, Direction.NEUTRAL, 0.0,
                            {"rsi": rsi, "distance_atr": distance_from_ema})
