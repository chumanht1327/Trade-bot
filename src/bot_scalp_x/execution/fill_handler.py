"""Partial fill accumulation state machine."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from bot_scalp_x.execution.schemas import ExecutionReport, Fill, OrderStatus


class FillHandler:
    """Accumulates partial fills until order is fully filled or cancelled."""

    def __init__(self, report: ExecutionReport) -> None:
        self._report = report
        self._filled_lots = 0.0
        self._target_lots = report.order.lot_size

    def apply_fill(self, price: Decimal, lots: float) -> ExecutionReport:
        fill = Fill(price=price, lots=lots, ts=datetime.now(tz=timezone.utc))
        self._report.fills.append(fill)
        self._filled_lots += lots

        # Weighted average fill price
        total_value = sum(float(f.price) * f.lots for f in self._report.fills)
        total_lots = sum(f.lots for f in self._report.fills)
        self._report.filled_price = Decimal(str(round(total_value / total_lots, 5)))
        self._report.filled_lots = total_lots

        if self._filled_lots >= self._target_lots * 0.999:
            self._report.status = OrderStatus.FILLED
        else:
            self._report.status = OrderStatus.PARTIAL

        return self._report

    @property
    def is_complete(self) -> bool:
        return self._report.status == OrderStatus.FILLED
