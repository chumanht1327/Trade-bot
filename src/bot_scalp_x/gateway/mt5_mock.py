"""Full async MT5 mock for Linux/CI. Mirrors the real gateway interface exactly."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Awaitable
import structlog

from bot_scalp_x.data.schemas import Tick
from bot_scalp_x.gateway.schemas import (
    MT5AccountInfo,
    MT5OrderResult,
    MT5SymbolInfo,
    ConnectionStatus,
)

log = structlog.get_logger(__name__)

_BASE_PRICES: dict[str, float] = {
    "XAUUSD": 1985.0,
    "NAS100": 17800.0,
    "EURUSD": 1.0850,
}

_TICKET_COUNTER = 10000


class MT5Mock:
    """Configurable mock: supports latency simulation, partial fills, rejections."""

    def __init__(
        self,
        simulate_latency_ms: float = 20.0,
        reject_probability: float = 0.0,
        partial_fill_probability: float = 0.0,
        account_equity: float = 10_000.0,
    ) -> None:
        self._latency = simulate_latency_ms / 1000.0
        self._reject_prob = reject_probability
        self._partial_prob = partial_fill_probability
        self._equity = account_equity
        self._balance = account_equity
        self._connected = False
        self._orders: dict[int, dict] = {}
        self._streaming: dict[str, asyncio.Task] = {}

    async def connect(self) -> bool:
        await asyncio.sleep(self._latency)
        self._connected = True
        log.info("mt5_mock_connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        for task in self._streaming.values():
            task.cancel()
        self._streaming.clear()

    async def get_account_info(self) -> MT5AccountInfo:
        await asyncio.sleep(self._latency)
        return MT5AccountInfo(
            login=99999,
            balance=self._balance,
            equity=self._equity,
            margin=0.0,
            free_margin=self._equity,
            currency="USD",
            leverage=100,
            server="mock-server",
        )

    async def get_symbol_info(self, symbol: str) -> MT5SymbolInfo:
        await asyncio.sleep(self._latency)
        base = _BASE_PRICES.get(symbol, 1.0)
        spread = {"XAUUSD": 0.5, "NAS100": 2.0, "EURUSD": 0.0001}.get(symbol, 0.0001)
        return MT5SymbolInfo(
            name=symbol,
            bid=base,
            ask=base + spread,
            spread=spread,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            point={"XAUUSD": 0.01, "NAS100": 0.1, "EURUSD": 0.00001}.get(symbol, 0.00001),
            digits={"XAUUSD": 2, "NAS100": 1, "EURUSD": 5}.get(symbol, 5),
        )

    async def place_order(self, order: object) -> MT5OrderResult:  # type: ignore[override]
        global _TICKET_COUNTER
        await asyncio.sleep(self._latency)

        if random.random() < self._reject_prob:
            return MT5OrderResult(ticket=0, price=0.0, volume=0.0, comment="rejected", retcode=10006)

        _TICKET_COUNTER += 1
        ticket = _TICKET_COUNTER
        from bot_scalp_x.execution.schemas import Order
        o: Order = order  # type: ignore[assignment]

        base = _BASE_PRICES.get(o.symbol, 1.0)
        slippage = random.uniform(-0.0002, 0.0002) * base
        fill_price = round(base + slippage, 5)

        filled_lots = float(o.lot_size)
        if random.random() < self._partial_prob:
            filled_lots = round(filled_lots * random.uniform(0.3, 0.9), 2)

        self._orders[ticket] = {
            "ticket": ticket,
            "symbol": o.symbol,
            "lots": filled_lots,
            "price": fill_price,
            "sl": float(o.sl_price) if o.sl_price else 0.0,
            "tp": float(o.tp_price) if o.tp_price else 0.0,
        }
        return MT5OrderResult(ticket=ticket, price=fill_price, volume=filled_lots, retcode=10009)

    async def cancel_order(self, ticket: int) -> bool:
        await asyncio.sleep(self._latency)
        if ticket in self._orders:
            del self._orders[ticket]
            return True
        return False

    async def get_open_positions(self) -> list[dict]:
        await asyncio.sleep(self._latency)
        return list(self._orders.values())

    async def subscribe_ticks(self, symbol: str, callback: Callable[[Tick], Awaitable[None]]) -> None:
        """Start a background task that emits synthetic ticks."""
        if symbol in self._streaming:
            return

        async def _stream() -> None:
            base = _BASE_PRICES.get(symbol, 1.0)
            while True:
                drift = random.gauss(0, base * 0.0001)
                base += drift
                bid = round(base, 5)
                spread = {"XAUUSD": 0.3, "NAS100": 1.5, "EURUSD": 0.00008}.get(symbol, 0.00008)
                ask = round(bid + spread, 5)
                tick = Tick(
                    symbol=symbol,
                    ts=datetime.now(tz=timezone.utc),
                    bid=Decimal(str(bid)),
                    ask=Decimal(str(ask)),
                    volume=random.uniform(1.0, 10.0),
                )
                try:
                    await callback(tick)
                except Exception:
                    log.exception("mock_tick_callback_error", symbol=symbol)
                await asyncio.sleep(0.05)  # 20 ticks/sec

        task = asyncio.create_task(_stream(), name=f"mock_tick_{symbol}")
        self._streaming[symbol] = task
        log.info("mock_tick_stream_started", symbol=symbol)
