from fastapi import APIRouter, Request
from bot_scalp_x.monitoring.health import readiness_check

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(request: Request) -> dict:
    return await readiness_check(request.app.state.pool, request.app.state.redis)
