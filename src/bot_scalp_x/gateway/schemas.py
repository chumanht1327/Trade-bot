"""Gateway-level data types for MT5 interactions."""

from dataclasses import dataclass, field
from enum import Enum


class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


@dataclass
class MT5AccountInfo:
    login: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    currency: str
    leverage: int
    server: str


@dataclass
class MT5SymbolInfo:
    name: str
    bid: float
    ask: float
    spread: float
    volume_min: float
    volume_max: float
    volume_step: float
    point: float
    digits: int


@dataclass
class MT5OrderResult:
    ticket: int
    price: float
    volume: float
    comment: str = ""
    retcode: int = 0

    @property
    def success(self) -> bool:
        return self.retcode == 10009  # TRADE_RETCODE_DONE
