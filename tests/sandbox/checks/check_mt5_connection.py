"""Check 1: MT5 connection + account info."""

from bot_scalp_x.gateway.mt5_mock import MT5Mock


async def check() -> str:
    gw = MT5Mock()
    assert await gw.connect(), "MT5 connect() returned False"
    info = await gw.get_account_info()
    assert info.login > 0, f"Unexpected login: {info.login}"
    assert info.equity > 0, f"Unexpected equity: {info.equity}"
    return f"Connected. Login={info.login}, Equity={info.equity}"
