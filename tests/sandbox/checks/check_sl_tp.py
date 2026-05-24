"""Check 4: Verify SL and TP are set on placed order."""

import uuid
from decimal import Decimal

from bot_scalp_x.execution.schemas import Order, OrderType
from bot_scalp_x.gateway.mt5_mock import MT5Mock
from bot_scalp_x.signals.schemas import Direction


async def check() -> str:
    gw = MT5Mock()
    await gw.connect()
    sl = Decimal("1980.00")
    tp = Decimal("1990.00")
    order = Order(
        id=uuid.uuid4(), symbol="XAUUSD", direction=Direction.LONG,
        order_type=OrderType.MARKET, lot_size=0.01,
        sl_price=sl, tp_price=tp,
        idempotency_key="sandbox_sl_tp_check",
    )
    result = await gw.place_order(order)
    assert result.success

    positions = await gw.get_open_positions()
    pos = next((p for p in positions if p["ticket"] == result.ticket), None)
    assert pos is not None, f"Ticket {result.ticket} not found in positions"
    assert abs(pos["sl"] - float(sl)) < 0.01, f"SL mismatch: expected {sl}, got {pos['sl']}"
    assert abs(pos["tp"] - float(tp)) < 0.01, f"TP mismatch: expected {tp}, got {pos['tp']}"
    return f"SL={pos['sl']}, TP={pos['tp']} verified for ticket={result.ticket}"
