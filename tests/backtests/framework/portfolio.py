"""Virtual portfolio for backtesting: tracks positions, P&L, equity curve."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from bot_scalp_x.signals.schemas import Direction

_SLIPPAGE_FACTOR = 0.0002  # 0.02% simulated slippage on fills


@dataclass
class VirtualPosition:
    symbol: str
    direction: Direction
    entry_price: float
    lot_size: float
    sl_price: float
    tp_price: float
    risk_pct: float
    trade_id: int


@dataclass
class ClosedTrade:
    symbol: str
    direction: Direction
    entry_price: float
    exit_price: float
    lot_size: float
    pnl: float
    bars_held: int
    exit_reason: str  # TP, SL, EOD


class VirtualPortfolio:
    def __init__(self, initial_equity: float = 10_000.0) -> None:
        self._equity = initial_equity
        self._initial = initial_equity
        self._positions: list[VirtualPosition] = []
        self._closed: list[ClosedTrade] = []
        self._trade_counter = 0

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def closed_trades(self) -> list[ClosedTrade]:
        return self._closed

    def open_position(
        self,
        symbol: str,
        direction: Direction,
        price: float,
        lot_size: float,
        sl: float,
        tp: float,
        risk_pct: float,
    ) -> int:
        # Simulate entry slippage
        if direction == Direction.LONG:
            fill_price = price * (1 + _SLIPPAGE_FACTOR)
        else:
            fill_price = price * (1 - _SLIPPAGE_FACTOR)

        self._trade_counter += 1
        pos = VirtualPosition(symbol, direction, fill_price, lot_size, sl, tp, risk_pct, self._trade_counter)
        self._positions.append(pos)
        return self._trade_counter

    def update_prices(self, symbol: str, bid: float, ask: float, bar_count: int) -> None:
        """Check open positions for SL/TP hits."""
        price = (bid + ask) / 2
        to_close = []

        for pos in self._positions:
            if pos.symbol != symbol:
                continue
            if pos.direction == Direction.LONG:
                if bid <= pos.sl_price:
                    self._close_position(pos, bid, "SL", bar_count)
                    to_close.append(pos)
                elif ask >= pos.tp_price:
                    self._close_position(pos, ask, "TP", bar_count)
                    to_close.append(pos)
            else:
                if ask >= pos.sl_price:
                    self._close_position(pos, ask, "SL", bar_count)
                    to_close.append(pos)
                elif bid <= pos.tp_price:
                    self._close_position(pos, bid, "TP", bar_count)
                    to_close.append(pos)

        for pos in to_close:
            self._positions.remove(pos)

    def _close_position(self, pos: VirtualPosition, exit_price: float, reason: str, bar_count: int) -> None:
        if pos.direction == Direction.LONG:
            pnl = (exit_price - pos.entry_price) * pos.lot_size * 100  # simplified
        else:
            pnl = (pos.entry_price - exit_price) * pos.lot_size * 100

        self._equity += pnl
        self._closed.append(ClosedTrade(
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            lot_size=pos.lot_size,
            pnl=pnl,
            bars_held=bar_count,
            exit_reason=reason,
        ))
