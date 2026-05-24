"""aiomql-based async MT5 gateway for Windows live trading."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Awaitable

from bot_scalp_x.data.schemas import Tick
from bot_scalp_x.gateway.schemas import MT5AccountInfo, MT5OrderResult, MT5SymbolInfo

log = logging.getLogger(__name__)


class AiomqlGateway:
    """
    Async MT5 gateway backed by aiomql (Windows only, pip install -e '.[live]').
    Exposes the same interface as MT5Mock for drop-in use via factory.py.
    """

    def __init__(
        self,
        login: int,
        password: str,
        server: str,
        timeout_ms: int = 60_000,
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._timeout = timeout_ms / 1000.0
        self._mt: Any = None
        self._account: Any = None
        self._streaming: dict[str, asyncio.Task] = {}

    async def connect(self) -> bool:
        try:
            from aiomql import MetaTrader  # type: ignore[import]

            self._mt = MetaTrader()
            ok = await self._mt.initialize(
                login=self._login,
                password=self._password,
                server=self._server,
            )
            if not ok:
                log.error("aiomql: initialize failed for server=%s", self._server)
                return False

            from aiomql import Account  # type: ignore[import]

            self._account = Account()
            await self._account.refresh()
            log.info("aiomql: connected to %s as %d", self._server, self._login)
            return True
        except Exception:
            log.exception("aiomql: connect failed")
            return False

    async def disconnect(self) -> None:
        for task in self._streaming.values():
            task.cancel()
        self._streaming.clear()
        try:
            if self._mt is not None:
                self._mt.shutdown()
        except Exception:
            pass

    async def get_account_info(self) -> MT5AccountInfo:
        if self._account is None:
            return MT5AccountInfo(
                login=self._login, balance=0.0, equity=0.0,
                margin=0.0, free_margin=0.0, currency="USD", leverage=1, server=self._server,
            )
        try:
            from aiomql import Account  # type: ignore[import]

            await self._account.refresh()
            return MT5AccountInfo(
                login=self._login,
                balance=float(self._account.balance),
                equity=float(self._account.equity),
                margin=float(getattr(self._account, "margin", 0.0)),
                free_margin=float(getattr(self._account, "margin_free", 0.0)),
                currency=str(self._account.currency),
                leverage=int(getattr(self._account, "leverage", 1)),
                server=self._server,
            )
        except Exception:
            log.warning("aiomql: get_account_info failed", exc_info=True)
            return MT5AccountInfo(
                login=self._login, balance=0.0, equity=0.0,
                margin=0.0, free_margin=0.0, currency="USD", leverage=1, server=self._server,
            )

    async def get_symbol_info(self, symbol: str) -> MT5SymbolInfo:
        try:
            from aiomql import Symbol  # type: ignore[import]

            sym = Symbol(name=symbol)
            await sym.init()
            tick = await sym.info_tick()
            return MT5SymbolInfo(
                name=symbol,
                bid=float(tick.bid) if tick else 0.0,
                ask=float(tick.ask) if tick else 0.0,
                spread=float(getattr(sym, "spread", 0)) * float(getattr(sym, "point", 1e-5)),
                volume_min=float(getattr(sym, "volume_min", 0.01)),
                volume_max=float(getattr(sym, "volume_max", 100.0)),
                volume_step=float(getattr(sym, "volume_step", 0.01)),
                point=float(getattr(sym, "point", 1e-5)),
                digits=int(getattr(sym, "digits", 5)),
            )
        except Exception:
            log.warning("aiomql: get_symbol_info failed for %s", symbol, exc_info=True)
            return MT5SymbolInfo(
                name=symbol, bid=0.0, ask=0.0, spread=0.0,
                volume_min=0.01, volume_max=100.0, volume_step=0.01, point=1e-5, digits=5,
            )

    async def place_order(self, order: object) -> MT5OrderResult:
        try:
            from aiomql import Order, OrderType, TradeAction  # type: ignore[import]
            from bot_scalp_x.execution.schemas import Order as ExecOrder

            o: ExecOrder = order  # type: ignore[assignment]
            is_long = str(o.direction).upper() == "LONG"

            mt5_order = Order(
                action=TradeAction.DEAL,
                symbol=o.symbol,
                volume=float(o.lot_size),
                type=OrderType.BUY if is_long else OrderType.SELL,
                sl=float(o.sl_price) if o.sl_price else 0.0,
                tp=float(o.tp_price) if o.tp_price else 0.0,
                comment=f"BSX:{str(getattr(o, 'idem_key', ''))[:8]}",
            )
            result = await mt5_order.send()

            if result.retcode == 10009:  # TRADE_RETCODE_DONE
                return MT5OrderResult(
                    ticket=int(result.order),
                    price=float(result.price),
                    volume=float(result.volume),
                    retcode=result.retcode,
                    comment=str(result.comment or ""),
                )
            return MT5OrderResult(
                ticket=0,
                price=0.0,
                volume=0.0,
                retcode=int(result.retcode),
                comment=str(result.comment or "REJECTED"),
            )
        except Exception:
            log.exception("aiomql: place_order failed")
            return MT5OrderResult(ticket=0, price=0.0, volume=0.0, retcode=-1, comment="exception")

    async def cancel_order(self, ticket: int) -> bool:
        try:
            from aiomql import Order, TradeAction  # type: ignore[import]

            cancel_req = Order(action=TradeAction.REMOVE, order=ticket)
            result = await cancel_req.send()
            return int(result.retcode) in (10009, 10007)
        except Exception:
            log.warning("aiomql: cancel_order %d failed", ticket, exc_info=True)
            return False

    async def get_open_positions(self) -> list[dict]:
        try:
            from aiomql import Positions  # type: ignore[import]

            positions = Positions()
            pos_list = await positions.get_positions()
            return [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "lots": p.volume,
                    "price": p.price_open,
                    "sl": p.sl,
                    "tp": p.tp,
                }
                for p in (pos_list or [])
            ]
        except Exception:
            log.warning("aiomql: get_open_positions failed", exc_info=True)
            return []

    async def subscribe_ticks(
        self, symbol: str, callback: Callable[[Tick], Awaitable[None]]
    ) -> None:
        """Poll at 10 Hz via aiomql Symbol.info_tick() and emit Tick objects."""
        if symbol in self._streaming:
            return

        async def _poll() -> None:
            try:
                from aiomql import Symbol  # type: ignore[import]

                sym = Symbol(name=symbol)
                await sym.init()
                while True:
                    try:
                        raw = await sym.info_tick()
                        if raw:
                            t = Tick(
                                symbol=symbol,
                                ts=datetime.fromtimestamp(raw.time, tz=timezone.utc),
                                bid=Decimal(str(raw.bid)),
                                ask=Decimal(str(raw.ask)),
                                volume=float(raw.volume),
                            )
                            await callback(t)
                    except Exception:
                        log.debug("aiomql: tick poll error for %s", symbol, exc_info=True)
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(_poll(), name=f"aiomql_tick_{symbol}")
        self._streaming[symbol] = task
        log.info("aiomql: tick stream started for %s", symbol)
