from fastapi import APIRouter, Request
from bot_scalp_x.risk.drawdown import DrawdownTracker
from bot_scalp_x.risk.kill_switch import KillSwitch
from bot_scalp_x.risk.consecutive_loss import ConsecutiveLossTracker
from bot_scalp_x.config import get_settings

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status")
async def risk_status(request: Request) -> dict:
    cfg = get_settings()
    redis = request.app.state.redis
    ks = KillSwitch(redis, cfg.risk.max_latency_ms)
    dd = DrawdownTracker(redis, cfg.risk.daily_dd_limit_pct, cfg.risk.weekly_dd_limit_pct)
    loss = ConsecutiveLossTracker(redis, cfg.risk.max_consecutive_losses)

    daily_dd, weekly_dd = await dd.get_current()
    return {
        "kill_switch_active": await ks.is_active(),
        "daily_dd_pct": daily_dd,
        "weekly_dd_pct": weekly_dd,
        "consecutive_losses": await loss.get_count(),
        "limits": {
            "daily_dd_pct": cfg.risk.daily_dd_limit_pct,
            "weekly_dd_pct": cfg.risk.weekly_dd_limit_pct,
            "max_consecutive_losses": cfg.risk.max_consecutive_losses,
        },
    }
