"""Check 3: Place then cancel an order."""

import uuid
from decimal import Decimal

from bot_scalp_x.execution.schemas import Order, OrderType
from bot_scalp_x.gateway.mt5_mock import MT5Mock
from bot_scalp_x.signals.schemas import Direction


async def check() -> str:
    gw = MT5Mock()
    await gw.connect()
    order = Order(
        id=uuid.uuid4(), symbol="EURUSD", direction=Direction.SHORT,
        order_type=OrderType.MARKET, lot_size=0.01,
        sl_price=Decimal("1.0900"), tp_price=Decimal("1.0800"),
        idempotency_key="sandbox_cancel_check",
    )
    result = await gw.place_order(order)
    assert result.success, f"Placement failed: {result.retcode}"
    cancelled = await gw.cancel_order(result.ticket)
    assert cancelled, f"Cancel returned False for ticket {result.ticket}"
    positions = await gw.get_open_positions()
    ticket_exists = any(p.get("ticket") == result.ticket for p in positions)
    assert not ticket_exists, "Cancelled order still in open positions"
    return f"Placed ticket={result.ticket}, successfully cancelled"
