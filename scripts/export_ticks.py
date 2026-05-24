"""Export ticks from PostgreSQL to parquet for backtesting."""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

import pandas as pd

from bot_scalp_x.database.connection import close_pool, get_pool
from bot_scalp_x.database.repositories.tick_repo import get_ticks
from bot_scalp_x.logging_config import configure_logging

configure_logging("INFO", "console")


async def export(symbol: str, start: datetime, end: datetime, output: Path) -> None:
    pool = await get_pool()
    rows = await get_ticks(pool, symbol, start, end, limit=10_000_000)
    df = pd.DataFrame(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)
    print(f"Exported {len(df)} rows to {output}")
    await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=Path("datasets/processed/ticks.parquet"))
    args = parser.parse_args()

    asyncio.run(export(
        args.symbol,
        datetime.fromisoformat(args.start),
        datetime.fromisoformat(args.end),
        args.output,
    ))
