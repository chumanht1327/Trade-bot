"""Async tick ingestion loop: gateway → buffer → feature engine → downstream."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

import structlog

from bot_scalp_x.data.feature_engine import FeatureEngine
from bot_scalp_x.data.schemas import FeatureRow, Tick
from bot_scalp_x.data.tick_buffer import TickBuffer

log = structlog.get_logger(__name__)


class TickCollector:
    """Runs one async task per symbol; dispatches to feature engine and callback."""

    def __init__(
        self,
        buffer: TickBuffer,
        on_feature_row: Callable[[FeatureRow], Awaitable[None]],
        atr_period: int = 14,
    ) -> None:
        self._buffer = buffer
        self._on_feature_row = on_feature_row
        self._engines: dict[str, FeatureEngine] = {}
        self._atr_period = atr_period

    def _engine_for(self, symbol: str) -> FeatureEngine:
        if symbol not in self._engines:
            self._engines[symbol] = FeatureEngine(symbol, self.atr_period)
        return self._engines[symbol]

    @property
    def atr_period(self) -> int:
        return self._atr_period

    async def process_tick(self, tick: Tick) -> None:
        try:
            await self._buffer.push(tick)
            row = self._engine_for(tick.symbol).update(tick)
            if row is not None:
                await self._on_feature_row(row)
        except Exception:
            log.exception("tick_processing_error", symbol=tick.symbol)

    async def run_mock_stream(self, symbol: str, gateway: object) -> None:
        """Drive the mock tick stream (or real MT5 stream) for a single symbol."""
        log.info("tick_stream_starting", symbol=symbol)
        await gateway.subscribe_ticks(symbol, self.process_tick)  # type: ignore[attr-defined]
