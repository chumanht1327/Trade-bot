"""ATR-based position sizing: derive SL distance → lot size for target risk %."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.signals.schemas import Direction

_SL_ATR_MULTIPLIER = 1.5
_TP_RR_RATIO = 2.0  # Reward:Risk ratio for TP placement
_MIN_LOT = 0.01
_MAX_LOT = 10.0

# Contract sizes: $ per point per lot
_CONTRACT_SIZE: dict[str, float] = {
    "XAUUSD": 100.0,   # 1 lot = 100 oz; 1 point = $1
    "NAS100": 1.0,     # 1 lot = 1 contract; 1 point = $1
    "EURUSD": 100_000.0,  # 1 lot = 100k EUR; 1 pip = $10
}

_POINT_SIZE: dict[str, float] = {
    "XAUUSD": 0.01,
    "NAS100": 0.1,
    "EURUSD": 0.00001,
}


def calculate_position(
    features: FeatureRow,
    direction: Direction,
    account_equity: float,
    risk_pct: float,
) -> tuple[float, Decimal, Decimal] | None:
    """
    Returns (lot_size, sl_price, tp_price) or None if ATR is too small to size.
    """
    atr = features.atr_14
    if atr <= 0:
        return None

    price = float(features.tick.mid)
    symbol = features.symbol
    point = _POINT_SIZE.get(symbol, 0.00001)
    contract = _CONTRACT_SIZE.get(symbol, 1.0)

    sl_distance = atr * _SL_ATR_MULTIPLIER  # in price units
    risk_amount = account_equity * (risk_pct / 100.0)

    # lot_size × contract_size × sl_distance / point ≈ risk_amount
    dollar_per_lot_per_point = contract * point
    if dollar_per_lot_per_point <= 0 or sl_distance <= 0:
        return None

    sl_pts = sl_distance / point
    lot_size = risk_amount / (sl_pts * dollar_per_lot_per_point)
    lot_size = max(_MIN_LOT, min(_MAX_LOT, round(lot_size, 2)))

    if direction == Direction.LONG:
        sl = Decimal(str(round(price - sl_distance, 5)))
        tp = Decimal(str(round(price + sl_distance * _TP_RR_RATIO, 5)))
    else:
        sl = Decimal(str(round(price + sl_distance, 5)))
        tp = Decimal(str(round(price - sl_distance * _TP_RR_RATIO, 5)))

    return lot_size, sl, tp
