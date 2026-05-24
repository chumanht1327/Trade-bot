"""Check 2: Place a market order and verify ticket returned."""

import uuid
from decimal import Decimal

from bot_scalp_x.execution.schemas import Order, OrderType
from bot_scalp_x.gateway.mt5_mock import MT5Mock
from bot_scalp_x.signals.schemas import Direction


async def check() -> str:
    gw = MT5Mock()
    await gw.connect()
    order = Order(
        id=uuid.uuid4(), symbol="XAUUSD", direction=Direction.LONG,
        order_type=OrderType.MARKET, lot_size=0.01,
        sl_price=Decimal("1980.0"), tp_price=Decimal("1990.0"),
        idempotency_key="sandbox_place_order_check",
    )
    result = await gw.place_order(order)
    assert result.success, f"Order rejected with retcode {result.retcode}"
    assert result.ticket > 0, f"Expected ticket > 0, got {result.ticket}"
    assert result.price > 0, f"Expected fill price > 0"
    return f"Order placed. Ticket={result.ticket}, Price={result.price}"
