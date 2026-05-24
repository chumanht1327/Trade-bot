"""Walk-forward backtest: strict temporal train/test split, no lookahead bias."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd

from tests.backtests.run_backtest import run


def walk_forward(
    parquet_path: Path,
    symbol: str,
    train_months: int = 3,
    test_months: int = 1,
    initial_equity: float = 10_000.0,
) -> list[dict]:
    """Split dataset into rolling windows and run backtest on each test window."""
    df = pd.read_parquet(parquet_path)
    df = df[df["symbol"] == symbol].sort_values("ts").reset_index(drop=True)
    df["ts"] = pd.to_datetime(df["ts"])

    start = df["ts"].min()
    end = df["ts"].max()

    results = []
    window_start = start

    while True:
        train_end = window_start + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)

        if test_end > end:
            break

        test_df = df[(df["ts"] >= train_end) & (df["ts"] < test_end)]
        if len(test_df) < 100:
            break

        # Write test window to temp parquet for the runner
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            tmp = Path(f.name)
        test_df.to_parquet(tmp)

        summary = asyncio.run(run(symbol, tmp, initial_equity))
        summary["window_start"] = str(train_end.date())
        summary["window_end"] = str(test_end.date())
        results.append(summary)
        tmp.unlink(missing_ok=True)

        window_start += pd.DateOffset(months=test_months)

    passing = sum(1 for r in results if r["passes"])
    print(json.dumps({
        "symbol": symbol,
        "windows": len(results),
        "passing_windows": passing,
        "pass_rate": round(passing / len(results), 2) if results else 0.0,
        "windows_detail": results,
    }, indent=2))

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    walk_forward(args.data, args.symbol)
