"""VWAP Rejection signal: price touches VWAP then shows volume-confirmed rejection."""

from __future__ import annotations

import numpy as np

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.signals.base import BaseSignal
from bot_scalp_x.signals.schemas import Direction, SignalResult

_VWAP_TOUCH_ATR_MULT = 0.5
_VOLUME_SPIKE_FACTOR = 1.5


class VWAPRejectionSignal(BaseSignal):
    """
    Long: price dips to VWAP (within 0.5 ATR) with volume spike, then closes above VWAP.
    Short: price rises to VWAP with volume spike, then closes below VWAP.
    """

    async def evaluate(self, features: FeatureRow, history: list[FeatureRow]) -> SignalResult:
        if len(history) < 10:
            return SignalResult("VWAP_REJECTION", False, Direction.NEUTRAL, 0.0)

        recent = history[-10:]
        vols = np.array([r.tick.volume for r in recent])
        avg_vol = float(np.mean(vols[:-1])) if len(vols) > 1 else 1.0

        price = float(features.tick.mid)
        vwap = features.vwap
        atr = features.atr_14
        cur_vol = features.tick.volume

        distance_to_vwap = abs(price - vwap)
        at_vwap = distance_to_vwap < atr * _VWAP_TOUCH_ATR_MULT
        volume_spike = cur_vol > avg_vol * _VOLUME_SPIKE_FACTOR and avg_vol > 0

        if not (at_vwap and volume_spike):
            return SignalResult("VWAP_REJECTION", False, Direction.NEUTRAL, 0.0,
                                {"at_vwap": at_vwap, "volume_spike": volume_spike,
                                 "distance_vwap": distance_to_vwap, "atr": atr})

        # Determine direction from VWAP approach
        prev_prices = [float(r.tick.mid) for r in recent[:-1]]
        prev_avg = float(np.mean(prev_prices)) if prev_prices else price

        confidence = min(1.0, (cur_vol / (avg_vol + 1e-10) - 1.0) * 0.5)

        if prev_avg < vwap and price >= vwap:
            # Was below, now at/above VWAP → bullish rejection
            return SignalResult("VWAP_REJECTION", True, Direction.LONG, confidence,
                                {"vwap": vwap, "vol_ratio": cur_vol / (avg_vol + 1e-10)})
        if prev_avg > vwap and price <= vwap:
            # Was above, now at/below VWAP → bearish rejection
            return SignalResult("VWAP_REJECTION", True, Direction.SHORT, confidence,
                                {"vwap": vwap, "vol_ratio": cur_vol / (avg_vol + 1e-10)})

        return SignalResult("VWAP_REJECTION", False, Direction.NEUTRAL, 0.0)
