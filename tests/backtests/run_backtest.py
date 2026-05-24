"""CLI backtest runner: tick replay → signals → risk → virtual portfolio → metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from bot_scalp_x.data.feature_engine import FeatureEngine
from bot_scalp_x.data.schemas import FeatureRow
from bot_scalp_x.regime.classifier import RegimeClassifier
from bot_scalp_x.risk.position_sizer import calculate_position
from bot_scalp_x.signals.aggregator import SignalAggregator
from tests.backtests.framework.metrics import backtest_summary
from tests.backtests.framework.portfolio import VirtualPortfolio
from tests.backtests.framework.tick_replay import replay_ticks


async def run(symbol: str, parquet_path: Path, initial_equity: float = 10_000.0) -> dict:
    engine = FeatureEngine(symbol)
    classifier = RegimeClassifier(symbol)
    aggregator = SignalAggregator(min_votes=2)
    portfolio = VirtualPortfolio(initial_equity)
    history: list[FeatureRow] = []
    equity_curve: list[float] = [initial_equity]
    bar = 0

    async for tick in replay_ticks(parquet_path, symbol):
        row = engine.update(tick)
        if row is None:
            continue

        # Attach regime (heuristic if no trained model)
        regime, conf = classifier.predict(history[-100:] if len(history) >= 10 else history)
        row.regime = regime
        row.regime_confidence = conf
        history.append(row)
        if len(history) > 500:
            history.pop(0)

        portfolio.update_prices(symbol, float(tick.bid), float(tick.ask), bar)

        signal = await aggregator.evaluate(row, history)
        if signal is not None:
            result = calculate_position(row, signal.direction, portfolio.equity, 0.25)
            if result:
                lot_size, sl, tp = result
                portfolio.open_position(
                    symbol, signal.direction, float(tick.ask if signal.direction.value == "LONG" else tick.bid),
                    lot_size, float(sl), float(tp), 0.25,
                )

        equity_curve.append(portfolio.equity)
        bar += 1

    summary = backtest_summary(portfolio.closed_trades, equity_curve)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="BOT-SCALP-X backtester")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--data", type=Path, required=True, help="Path to tick parquet file")
    parser.add_argument("--equity", type=float, default=10_000.0)
    args = parser.parse_args()

    summary = asyncio.run(run(args.symbol, args.data, args.equity))
    print(json.dumps(summary, indent=2))

    if not summary["passes"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
