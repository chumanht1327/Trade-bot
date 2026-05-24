"""vectorbt-based signal parameter grid search over EMA fast/slow combos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _resample_to_ohlcv(ticks_df: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """Resample tick DataFrame (with 'mid' and 'volume' columns) to OHLCV bars."""
    ohlcv = ticks_df["mid"].resample(freq).ohlc()
    ohlcv["volume"] = ticks_df["volume"].resample(freq).sum()
    return ohlcv.dropna()


def grid_search_ema(
    parquet_path: Path,
    symbol: str,
    ema_fast_range: range = range(5, 20, 2),
    ema_slow_range: range = range(15, 50, 5),
    freq: str = "1min",
) -> pd.DataFrame:
    """
    Sweep EMA(fast)/EMA(slow) crossover parameter combos using vectorbt.

    Returns a DataFrame sorted by Sharpe ratio (descending) with columns:
    ema_fast, ema_slow, total_return, sharpe, max_dd, win_rate.

    Requires: pip install -e '.[optimize]'
    """
    try:
        import vectorbt as vbt  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "vectorbt is required for grid search. Install with: pip install -e '.[optimize]'"
        ) from exc

    ticks_df = pd.read_parquet(parquet_path)

    if "mid" not in ticks_df.columns:
        if "bid" in ticks_df.columns and "ask" in ticks_df.columns:
            ticks_df["mid"] = (ticks_df["bid"] + ticks_df["ask"]) / 2.0
        else:
            raise ValueError("Parquet file must have 'mid' or 'bid'+'ask' columns")

    if not isinstance(ticks_df.index, pd.DatetimeIndex):
        if "ts" in ticks_df.columns:
            ticks_df = ticks_df.set_index("ts")
        ticks_df.index = pd.to_datetime(ticks_df.index, utc=True)

    ohlcv = _resample_to_ohlcv(ticks_df, freq)
    close = ohlcv["close"]

    results = []
    for fast in ema_fast_range:
        for slow in ema_slow_range:
            if fast >= slow:
                continue
            try:
                fast_ma = vbt.MA.run(close, window=fast, ewm=True)
                slow_ma = vbt.MA.run(close, window=slow, ewm=True)

                entries = fast_ma.ma_crossed_above(slow_ma)
                exits = fast_ma.ma_crossed_below(slow_ma)

                pf = vbt.Portfolio.from_signals(close, entries, exits, freq=freq)
                stats = pf.stats()

                results.append(
                    {
                        "ema_fast": fast,
                        "ema_slow": slow,
                        "total_return": float(stats.get("Total Return [%]", 0.0)),
                        "sharpe": float(stats.get("Sharpe Ratio", 0.0)),
                        "max_dd": float(stats.get("Max Drawdown [%]", 100.0)),
                        "win_rate": float(stats.get("Win Rate [%]", 0.0)),
                    }
                )
            except Exception:
                continue

    if not results:
        return pd.DataFrame(
            columns=["ema_fast", "ema_slow", "total_return", "sharpe", "max_dd", "win_rate"]
        )

    return pd.DataFrame(results).sort_values("sharpe", ascending=False).reset_index(drop=True)


def optimal_params(results: pd.DataFrame) -> dict[str, Any]:
    """
    Extract the best parameter set: highest Sharpe with max drawdown < 10%.
    Falls back to global best Sharpe if no row passes the DD filter.
    """
    if results.empty:
        return {}

    filtered = results[results["max_dd"] < 10.0]
    best = filtered.iloc[0] if not filtered.empty else results.iloc[0]

    return {
        "ema_fast": int(best["ema_fast"]),
        "ema_slow": int(best["ema_slow"]),
        "sharpe": round(float(best["sharpe"]), 3),
        "total_return_pct": round(float(best["total_return"]), 2),
        "max_dd_pct": round(float(best["max_dd"]), 2),
        "win_rate_pct": round(float(best["win_rate"]), 2),
    }
