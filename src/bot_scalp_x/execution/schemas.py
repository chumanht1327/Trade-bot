"""Execution layer data contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from bot_scalp_x.signals.schemas import Direction


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


@dataclass
class Order:
    id: UUID
    symbol: str
    direction: Direction
    order_type: OrderType
    lot_size: float
    sl_price: Decimal
    tp_price: Decimal
    idempotency_key: str
    limit_price: Decimal | None = None
    signal_id: int | None = None


@dataclass
class Fill:
    price: Decimal
    lots: float
    ts: datetime


@dataclass
class ExecutionReport:
    order: Order
    status: OrderStatus
    filled_price: Decimal | None = None
    filled_lots: float | None = None
    slippage_pts: float | None = None
    latency_ms: float = 0.0
    mt5_ticket: int | None = None
    fills: list[Fill] = field(default_factory=list)
    attempts: int = 1
    error: str | None = None
    trade_id: int | None = None  # Set after DB insert
