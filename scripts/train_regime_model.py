"""CLI: train regime classifier for a symbol from parquet tick data."""

import argparse
from pathlib import Path

from bot_scalp_x.logging_config import configure_logging
from bot_scalp_x.regime.trainer import train

configure_logging("INFO", "console")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train regime classifier")
    parser.add_argument("--symbol", required=True, help="Symbol: XAUUSD, NAS100, EURUSD")
    parser.add_argument("--data", type=Path, required=True, help="Path to tick parquet file")
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=6)
    args = parser.parse_args()

    train(args.symbol, args.data, args.n_estimators, args.max_depth)
