from fastapi import APIRouter, Request
from bot_scalp_x.database.repositories.signal_repo import get_recent_signals

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/recent")
async def recent_signals(request: Request, symbol: str = "XAUUSD", limit: int = 50) -> list[dict]:
    return await get_recent_signals(request.app.state.pool, symbol, limit)
