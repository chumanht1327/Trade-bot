"""Backtest performance metrics: Profit Factor, Sharpe, Max Drawdown, Expectancy."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tests.backtests.framework.portfolio import ClosedTrade


def profit_factor(trades: list[ClosedTrade]) -> float:
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 1.0
    return gross_profit / gross_loss


def sharpe_ratio(trades: list[ClosedTrade], risk_free_rate: float = 0.0) -> float:
    if len(trades) < 2:
        return 0.0
    returns = np.array([t.pnl for t in trades])
    excess = returns - risk_free_rate
    std = np.std(excess)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(252))  # Annualized


def max_drawdown_pct(equity_curve: list[float]) -> float:
    """Maximum peak-to-trough drawdown as a percentage."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100.0
        max_dd = max(max_dd, dd)
    return max_dd


def expectancy(trades: list[ClosedTrade]) -> float:
    """Average P&L per trade (positive = profitable system)."""
    if not trades:
        return 0.0
    return sum(t.pnl for t in trades) / len(trades)


def win_rate(trades: list[ClosedTrade]) -> float:
    if not trades:
        return 0.0
    return sum(1 for t in trades if t.pnl > 0) / len(trades)


def backtest_summary(trades: list[ClosedTrade], equity_curve: list[float]) -> dict:
    return {
        "total_trades": len(trades),
        "profit_factor": round(profit_factor(trades), 3),
        "sharpe_ratio": round(sharpe_ratio(trades), 3),
        "max_drawdown_pct": round(max_drawdown_pct(equity_curve), 3),
        "expectancy": round(expectancy(trades), 2),
        "win_rate": round(win_rate(trades), 3),
        "passes": (
            profit_factor(trades) > 1.5
            and sharpe_ratio(trades) > 1.5
            and max_drawdown_pct(equity_curve) < 10.0
            and expectancy(trades) > 0
        ),
    }


def generate_tearsheet(
    trades: list[ClosedTrade],
    equity_curve: list[float],
    output_path: str | Path = "backtest_report.html",
    title: str = "BOT-SCALP-X",
) -> None:
    """Generate an HTML tearsheet via quantstats. Silently skips if not installed."""
    try:
        import pandas as pd
        import quantstats as qs  # type: ignore[import]

        if not trades or len(equity_curve) < 2:
            return

        # Convert per-trade P&L to percentage returns against prior equity
        pnl_series = []
        eq = equity_curve[0]
        for trade in trades:
            ret = trade.pnl / eq if eq != 0.0 else 0.0
            pnl_series.append(ret)
            eq += trade.pnl

        returns = pd.Series(pnl_series)
        qs.reports.html(returns, output=str(output_path), title=title)
    except ImportError:
        pass
