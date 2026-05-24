"""Return real or mock MT5 gateway based on config and platform."""

import importlib.util
import sys

from bot_scalp_x.config import get_settings


def create_gateway() -> object:
    settings = get_settings()

    if settings.mt5.mock_mode or sys.platform != "win32":
        from bot_scalp_x.gateway.mt5_mock import MT5Mock
        return MT5Mock()

    # On Windows live mode: prefer aiomql (async-native) if installed
    if importlib.util.find_spec("aiomql") is not None:
        from bot_scalp_x.gateway.aiomql_gateway import AiomqlGateway
        return AiomqlGateway(
            login=settings.mt5.login,
            password=settings.mt5.password.get_secret_value(),
            server=settings.mt5.server,
            timeout_ms=settings.mt5.timeout_ms,
        )

    from bot_scalp_x.gateway.mt5_gateway import MT5Gateway
    return MT5Gateway(
        login=settings.mt5.login,
        password=settings.mt5.password.get_secret_value(),
        server=settings.mt5.server,
        timeout_ms=settings.mt5.timeout_ms,
    )
