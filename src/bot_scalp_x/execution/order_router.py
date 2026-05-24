"""Market vs Limit order routing based on spread and urgency."""

from __future__ import annotations

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.execution.schemas import OrderType
from bot_scalp_x.risk.schemas import RiskDecision

_LIMIT_SPREAD_THRESHOLD = 0.5  # If spread > 50% of ATR → prefer limit order


def route_order(decision: RiskDecision, features: FeatureRow) -> OrderType:
    """
    Use a limit order when spread is large relative to ATR (reduces fill cost).
    Use a market order for momentum signals that require immediate execution.
    """
    spread = float(features.tick.spread_pts)
    atr = features.atr_14

    if atr > 0 and spread / atr > _LIMIT_SPREAD_THRESHOLD:
        return OrderType.LIMIT

    # Momentum breakout signals benefit from immediate market execution
    momentum_signal = any(
        r.name == "MOMENTUM_BREAKOUT" and r.fired
        for r in decision.signal.signals
    )
    if momentum_signal:
        return OrderType.MARKET

    return OrderType.MARKET
