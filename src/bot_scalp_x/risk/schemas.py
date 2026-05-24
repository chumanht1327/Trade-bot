"""Risk engine data contracts."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from bot_scalp_x.signals.schemas import TradeSignal


class RiskStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED_SPREAD = "REJECTED_SPREAD"
    REJECTED_DAILY_DD = "REJECTED_DAILY_DD"
    REJECTED_WEEKLY_DD = "REJECTED_WEEKLY_DD"
    REJECTED_CONSECUTIVE_LOSS = "REJECTED_CONSECUTIVE_LOSS"
    REJECTED_KILL_SWITCH = "REJECTED_KILL_SWITCH"
    REJECTED_LATENCY = "REJECTED_LATENCY"
    REJECTED_NO_VOLATILITY = "REJECTED_NO_VOLATILITY"


@dataclass(frozen=True)
class RiskDecision:
    signal: TradeSignal
    status: RiskStatus
    lot_size: float | None
    sl_price: Decimal | None
    tp_price: Decimal | None
    risk_pct: float
    reason: str

    @property
    def approved(self) -> bool:
        return self.status == RiskStatus.APPROVED


@dataclass(frozen=True)
class KillSwitchEvent:
    reason: str
    triggered_at: str
    dd_pct: float | None = None
    latency_ms: float | None = None
    spread_pts: float | None = None
