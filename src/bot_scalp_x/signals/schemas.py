"""Signal contracts shared between signal implementations and the aggregator."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class SignalResult:
    name: str
    fired: bool
    direction: Direction
    confidence: float  # 0.0–1.0
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    ts: datetime
    direction: Direction
    votes: int
    confidence: float
    signals: tuple[SignalResult, ...]
    regime: str
    signal_id: int | None = None  # Set after DB insert
