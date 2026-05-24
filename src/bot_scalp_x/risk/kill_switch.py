"""Kill switch: activates on latency/spread/drawdown breach. State in Redis + DB."""

from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog

from bot_scalp_x.risk.schemas import KillSwitchEvent

log = structlog.get_logger(__name__)

_KEY = "risk:kill_switch"
_ACTIVE = "ACTIVE"
_INACTIVE = "INACTIVE"


class KillSwitch:
    def __init__(self, redis: aioredis.Redis, max_latency_ms: float) -> None:
        self._r = redis
        self._max_latency = max_latency_ms

    async def is_active(self) -> bool:
        val = await self._r.get(_KEY)
        return val == _ACTIVE.encode() if val else False

    async def activate(self, reason: str, **details: float) -> KillSwitchEvent:
        await self._r.set(_KEY, _ACTIVE)
        event = KillSwitchEvent(
            reason=reason,
            triggered_at=datetime.now(tz=timezone.utc).isoformat(),
            **{k: v for k, v in details.items() if k in {"dd_pct", "latency_ms", "spread_pts"}},
        )
        log.warning("kill_switch_activated", reason=reason, **details)
        return event

    async def deactivate(self) -> None:
        await self._r.set(_KEY, _INACTIVE)
        log.info("kill_switch_deactivated")

    async def restore_from_db(self, active: bool) -> None:
        """Called on startup to restore state from authoritative DB snapshot."""
        await self._r.set(_KEY, _ACTIVE if active else _INACTIVE)
        if active:
            log.warning("kill_switch_restored_active_from_db")

    async def check_latency(self, latency_ms: float) -> bool:
        """Returns True (and activates) if latency exceeds threshold."""
        if latency_ms > self._max_latency:
            await self.activate("latency_exceeded", latency_ms=latency_ms)
            return True
        return False

    async def check_spread(self, spread_pts: float, max_spread: float, symbol: str) -> bool:
        """Returns True (and activates) if spread exceeds symbol threshold."""
        if spread_pts > max_spread:
            await self.activate(f"spread_exceeded_{symbol}", spread_pts=spread_pts)
            return True
        return False
