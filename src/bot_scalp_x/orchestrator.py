"""Main bot loop: wires all components and manages per-symbol async tasks."""

from __future__ import annotations

import asyncio
import signal as os_signal
from datetime import date

import redis.asyncio as aioredis
import structlog
import uvloop

from bot_scalp_x.config import get_settings
from bot_scalp_x.data.collector import TickCollector
from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.data.tick_buffer import TickBuffer
from bot_scalp_x.database.connection import close_pool, get_pool
from bot_scalp_x.database.repositories.drawdown_repo import get_latest_snapshot
from bot_scalp_x.execution.engine import ExecutionEngine
from bot_scalp_x.gateway.factory import create_gateway
from bot_scalp_x.logging_config import configure_logging
from bot_scalp_x.regime.classifier import RegimeClassifier
from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
from bot_scalp_x.risk.drawdown import DrawdownTracker
from bot_scalp_x.risk.engine import RiskEngine
from bot_scalp_x.risk.kill_switch import KillSwitch
from bot_scalp_x.signals.aggregator import SignalAggregator

log = structlog.get_logger(__name__)

_HISTORY_WINDOW = 200  # Feature rows kept in memory per symbol


class BotOrchestrator:
    def __init__(self) -> None:
        self._cfg = get_settings()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._history: dict[str, list[FeatureRow]] = {s: [] for s in self._cfg.signals.symbols}
        self._classifiers: dict[str, RegimeClassifier] = {}

    async def _setup(self) -> None:
        self._pool = await get_pool()
        self._redis = aioredis.from_url(self._cfg.redis_url, decode_responses=False)
        self._gateway = create_gateway()
        await self._gateway.connect()  # type: ignore[attr-defined]

        buffer = TickBuffer(self._redis)
        kill_switch = KillSwitch(self._redis, self._cfg.risk.max_latency_ms)
        drawdown = DrawdownTracker(self._redis, self._cfg.risk.daily_dd_limit_pct, self._cfg.risk.weekly_dd_limit_pct)
        loss_tracker = ConsecutiveLossTracker(self._redis, self._cfg.risk.max_consecutive_losses)

        # Restore kill switch / DD state from DB on cold start (Redis may be empty)
        snapshot = await get_latest_snapshot(self._pool)
        if snapshot:
            await kill_switch.restore_from_db(bool(snapshot.get("kill_switch_active", False)))
            await drawdown.restore_from_snapshot(snapshot)
            await loss_tracker.set_count(snapshot.get("consecutive_losses", 0))
            log.info("state_restored_from_db", snapshot_date=str(snapshot.get("snapshot_date")))

        # Initialize drawdown baseline from MT5 equity
        account = await self._gateway.get_account_info()  # type: ignore[attr-defined]
        await drawdown.initialize_day(account.equity)

        self._risk = RiskEngine(kill_switch, drawdown, loss_tracker)
        self._execution = ExecutionEngine(self._gateway, self._pool, self._redis)
        self._aggregator = SignalAggregator(self._cfg.signals.min_votes_required)
        self._collector = TickCollector(buffer, self._on_feature_row)

        for symbol in self._cfg.signals.symbols:
            self._classifiers[symbol] = RegimeClassifier(symbol)

    async def _on_feature_row(self, row: FeatureRow) -> None:
        """Called for every new feature row produced by the data pipeline."""
        symbol = row.symbol
        history = self._history[symbol]
        history.append(row)
        if len(history) > _HISTORY_WINDOW:
            history.pop(0)

        # Attach regime to row (updated every 30s via regime_updater task)
        if history:
            regime_label, regime_conf = self._classifiers[symbol].predict(history)
            row.regime = regime_label
            row.regime_confidence = regime_conf

        signal = await self._aggregator.evaluate(row, history)
        if signal is None:
            return

        # Get current equity for position sizing
        account = await self._gateway.get_account_info()  # type: ignore[attr-defined]
        decision = await self._risk.evaluate(signal, row, account.equity)

        if not decision.approved:
            log.info("signal_rejected", symbol=symbol, reason=decision.reason)
            return

        await self._execution.submit(decision, row)

    async def run(self) -> None:
        configure_logging(self._cfg.log_level, self._cfg.log_format)
        log.info("bot_starting", symbols=self._cfg.signals.symbols, env=self._cfg.env)

        await self._setup()
        self._running = True

        loop = asyncio.get_running_loop()
        for sig in (os_signal.SIGTERM, os_signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown)

        tasks = [
            asyncio.create_task(
                self._collector.run_mock_stream(sym, self._gateway),
                name=f"tick_{sym}",
            )
            for sym in self._cfg.signals.symbols
        ]
        self._tasks = tasks

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            log.info("bot_shutdown_complete")
        finally:
            await close_pool()
            await self._redis.aclose()

    def _shutdown(self) -> None:
        log.info("bot_shutdown_requested")
        for t in self._tasks:
            t.cancel()


def main() -> None:
    uvloop.install()
    asyncio.run(BotOrchestrator().run())


if __name__ == "__main__":
    main()
