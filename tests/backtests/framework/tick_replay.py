"""Tick-by-tick event simulator. Reads parquet files and feeds ticks sequentially."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import AsyncIterator

import pandas as pd

from bot_scalp_x.data.schemas import Tick


async def replay_ticks(parquet_path: Path, symbol: str | None = None) -> AsyncIterator[Tick]:
    """Yield ticks from a parquet file in chronological order. No lookahead."""
    df = pd.read_parquet(parquet_path)
    if symbol:
        df = df[df["symbol"] == symbol]
    df = df.sort_values("ts").reset_index(drop=True)

    for _, row in df.iterrows():
        yield Tick(
            symbol=str(row["symbol"]),
            ts=pd.Timestamp(row["ts"]).to_pydatetime(),
            bid=Decimal(str(row["bid"])),
            ask=Decimal(str(row["ask"])),
            volume=float(row.get("volume", 0.0)),
        )


def load_tick_df(parquet_path: Path, symbol: str | None = None) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path)
    if symbol:
        df = df[df["symbol"] == symbol]
    return df.sort_values("ts").reset_index(drop=True)
