"""Feature computation: ATR (Wilder's), anchored VWAP, momentum, liquidity score, session."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
import pandas as pd

from bot_scalp_x.data.schemas import FeatureRow, Session, Tick


def _session_for(ts: datetime) -> Session:
    """Map UTC hour to trading session."""
    h = ts.hour
    if 7 <= h < 9:
        return Session.OVERLAP  # London/Asia overlap
    if 9 <= h < 13:
        return Session.LONDON
    if 13 <= h < 17:
        return Session.OVERLAP  # London/NY overlap
    if 17 <= h < 22:
        return Session.NY
    if 0 <= h < 7:
        return Session.TOKYO
    return Session.OFF


def _wilder_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
    """Wilder's smoothed ATR — expects arrays of length >= period + 1."""
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1]),
        ),
    )
    if len(tr) < period:
        return float(np.mean(tr)) if len(tr) > 0 else 0.0
    atr = float(np.mean(tr[:period]))
    for v in tr[period:]:
        atr = (atr * (period - 1) + v) / period
    return atr


def _anchored_vwap(prices: np.ndarray, volumes: np.ndarray) -> float:
    """Session-anchored VWAP from the start of the provided window."""
    if volumes.sum() == 0:
        return float(prices[-1]) if len(prices) else 0.0
    return float(np.sum(prices * volumes) / np.sum(volumes))


def _momentum(prices: np.ndarray, window: int) -> float:
    """Rate-of-change momentum: (price_now - price_n_ago) / price_n_ago."""
    if len(prices) <= window:
        return 0.0
    base = prices[-(window + 1)]
    if base == 0:
        return 0.0
    return float((prices[-1] - base) / base)


def _liquidity_score(spread_pts: Decimal, spread_history: list[float], volume: float, volume_history: list[float]) -> float:
    """Composite 0–1 score: 1 = tight spread + high volume = liquid."""
    if not spread_history or not volume_history:
        return 0.5

    spread_pct = min(float(spread_pts), max(spread_history)) / (max(spread_history) or 1.0)
    spread_score = 1.0 - min(spread_pct, 1.0)

    vol_pct = volume / (max(volume_history) or 1.0)
    vol_score = min(vol_pct, 1.0)

    return round(0.6 * spread_score + 0.4 * vol_score, 4)


class FeatureEngine:
    """Stateful feature engine; call update() per new tick."""

    def __init__(self, symbol: str, atr_period: int = 14, max_history: int = 500) -> None:
        self.symbol = symbol
        self.atr_period = atr_period
        self._ticks: list[Tick] = []
        self._max_history = max_history

    def update(self, tick: Tick) -> FeatureRow | None:
        """Add tick and return FeatureRow once enough history is available."""
        self._ticks.append(tick)
        if len(self._ticks) > self._max_history:
            self._ticks = self._ticks[-self._max_history :]

        n = len(self._ticks)
        min_required = self.atr_period + 2
        if n < min_required:
            return None

        mids = np.array([float(t.mid) for t in self._ticks])
        bids = np.array([float(t.bid) for t in self._ticks])
        asks = np.array([float(t.ask) for t in self._ticks])
        vols = np.array([t.volume for t in self._ticks])
        spreads = [float(t.spread_pts) for t in self._ticks]

        # Use mid as a proxy for high/low (tick data doesn't have OHLC bars)
        atr = _wilder_atr(asks, bids, mids, self.atr_period)
        vwap = _anchored_vwap(mids, vols)
        mom5 = _momentum(mids, 5)
        mom20 = _momentum(mids, 20)
        liq = _liquidity_score(tick.spread_pts, spreads[:-1], tick.volume, list(vols[:-1]))
        session = _session_for(tick.ts.replace(tzinfo=timezone.utc) if tick.ts.tzinfo is None else tick.ts)

        return FeatureRow(
            symbol=self.symbol,
            ts=tick.ts,
            tick=tick,
            atr_14=atr,
            vwap=vwap,
            momentum_5=mom5,
            momentum_20=mom20,
            liquidity_score=liq,
            session=session,
        )
