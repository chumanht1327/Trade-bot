"""Core data contracts shared by all pipeline stages."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Session(str, Enum):
    LONDON = "LONDON"
    NY = "NY"
    TOKYO = "TOKYO"
    OVERLAP = "OVERLAP"
    OFF = "OFF"


@dataclass(frozen=True)
class Tick:
    symbol: str
    ts: datetime
    bid: Decimal
    ask: Decimal
    volume: float = 0.0

    @property
    def spread_pts(self) -> Decimal:
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2


@dataclass
class FeatureRow:
    symbol: str
    ts: datetime
    tick: Tick
    atr_14: float
    vwap: float
    momentum_5: float
    momentum_20: float
    liquidity_score: float  # 0.0–1.0
    session: Session
    regime: str | None = None
    regime_confidence: float | None = None
