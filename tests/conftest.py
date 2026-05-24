"""Shared pytest fixtures: mock gateway, Redis client, DB pool, feature row factory."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable
from unittest.mock import AsyncMock

import pytest
import redis.asyncio as aioredis

from bot_scalp_x.data.schemas import FeatureRow, Session, Tick
from bot_scalp_x.gateway.mt5_mock import MT5Mock
from bot_scalp_x.signals.schemas import Direction


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def mock_mt5() -> MT5Mock:
    return MT5Mock(simulate_latency_ms=5.0)


@pytest.fixture
def sample_tick() -> Tick:
    return Tick(
        symbol="XAUUSD",
        ts=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        bid=Decimal("1984.50"),
        ask=Decimal("1985.00"),
        volume=5.0,
    )


@pytest.fixture
def feature_row_factory() -> Callable:
    """Returns a factory for building FeatureRow with sensible defaults."""

    def _build(
        symbol: str = "XAUUSD",
        bid: str = "1984.50",
        ask: str = "1985.00",
        atr_14: float = 2.5,
        vwap: float = 1984.80,
        momentum_5: float = 0.001,
        momentum_20: float = 0.0005,
        liquidity_score: float = 0.75,
        session: Session = Session.LONDON,
        regime: str = "TREND",
        volume: float = 5.0,
        ts: datetime | None = None,
    ) -> FeatureRow:
        if ts is None:
            ts = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        tick = Tick(symbol=symbol, ts=ts, bid=Decimal(bid), ask=Decimal(ask), volume=volume)
        return FeatureRow(
            symbol=symbol,
            ts=ts,
            tick=tick,
            atr_14=atr_14,
            vwap=vwap,
            momentum_5=momentum_5,
            momentum_20=momentum_20,
            liquidity_score=liquidity_score,
            session=session,
            regime=regime,
            regime_confidence=0.75,
        )

    return _build


@pytest.fixture
def long_feature_history(feature_row_factory: Callable) -> list[FeatureRow]:
    """50-bar history suitable for triggering signal evaluations."""
    from datetime import timedelta
    from decimal import Decimal
    import random

    rows = []
    base_bid = 1980.0
    for i in range(50):
        drift = random.gauss(0.02, 0.05)
        base_bid += drift
        rows.append(
            feature_row_factory(
                bid=str(round(base_bid, 2)),
                ask=str(round(base_bid + 0.5, 2)),
                momentum_5=0.001 + i * 0.00005,
                momentum_20=0.0005 + i * 0.00002,
                vwap=base_bid + 0.1,
                ts=datetime(2026, 5, 1, 10, tzinfo=timezone.utc) + timedelta(seconds=i * 5),
            )
        )
    return rows
