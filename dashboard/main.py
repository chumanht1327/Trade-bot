"""FastAPI dashboard application factory."""

from __future__ import annotations

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from prometheus_client import make_asgi_app

from bot_scalp_x.config import get_settings
from bot_scalp_x.database.connection import get_pool
from dashboard.routers import health, risk, signals, trades

app = FastAPI(title="BOT-SCALP-X Dashboard", version="0.1.0")

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(health.router)
app.include_router(trades.router)
app.include_router(risk.router)
app.include_router(signals.router)


@app.on_event("startup")
async def startup() -> None:
    cfg = get_settings()
    app.state.pool = await get_pool()
    app.state.redis = aioredis.from_url(cfg.redis_url, decode_responses=True)


@app.on_event("shutdown")
async def shutdown() -> None:
    from bot_scalp_x.database.connection import close_pool
    await close_pool()
    await app.state.redis.aclose()
