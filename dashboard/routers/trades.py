from fastapi import APIRouter, Query, Request
from bot_scalp_x.database.repositories.trade_repo import get_open_trades, get_trade

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
async def list_trades(request: Request, symbol: str | None = None) -> list[dict]:
    return await get_open_trades(request.app.state.pool, symbol)


@router.get("/{trade_id}")
async def get_trade_by_id(request: Request, trade_id: int) -> dict | None:
    return await get_trade(request.app.state.pool, trade_id)
