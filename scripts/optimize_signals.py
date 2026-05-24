"""CLI: EMA parameter grid search via vectorbt. Writes optimal params as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without editable install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grid-search optimal EMA signal parameters via vectorbt"
    )
    parser.add_argument("--symbol", default="XAUUSD", help="Trading symbol label (default: XAUUSD)")
    parser.add_argument("--data", type=Path, required=True, help="Tick parquet file path")
    parser.add_argument(
        "--freq", default="1min", help="Resample frequency for bar construction (default: 1min)"
    )
    parser.add_argument(
        "--fast-min", type=int, default=5, help="EMA fast period min (default: 5)"
    )
    parser.add_argument(
        "--fast-max", type=int, default=20, help="EMA fast period max exclusive (default: 20)"
    )
    parser.add_argument(
        "--fast-step", type=int, default=2, help="EMA fast period step (default: 2)"
    )
    parser.add_argument(
        "--slow-min", type=int, default=15, help="EMA slow period min (default: 15)"
    )
    parser.add_argument(
        "--slow-max", type=int, default=50, help="EMA slow period max exclusive (default: 50)"
    )
    parser.add_argument(
        "--slow-step", type=int, default=5, help="EMA slow period step (default: 5)"
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON results to file")
    args = parser.parse_args()

    from tests.backtests.optimize import grid_search_ema, optimal_params

    fast_range = range(args.fast_min, args.fast_max, args.fast_step)
    slow_range = range(args.slow_min, args.slow_max, args.slow_step)

    print(f"Scanning {len(fast_range) * len(slow_range)} EMA combos for {args.symbol}…")
    results = grid_search_ema(args.data, args.symbol, fast_range, slow_range, freq=args.freq)

    if results.empty:
        print("No valid parameter combinations found.")
        raise SystemExit(1)

    best = optimal_params(results)
    print(f"\nOptimal parameters:\n{json.dumps(best, indent=2)}")

    if args.output:
        args.output.write_text(json.dumps({"symbol": args.symbol, **best}, indent=2))
        print(f"\nSaved to {args.output}")

    print(f"\nTop 10 by Sharpe ratio:\n{results.head(10).to_string(index=False)}")


if __name__ == "__main__":
    main()
