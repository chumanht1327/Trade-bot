"""Single source of truth for all configuration. Every module imports from here."""

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MT5Settings(BaseModel):
    mock_mode: bool = True
    login: int = 0
    password: SecretStr = SecretStr("")
    server: str = "demo.broker.com"
    timeout_ms: int = 60000


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://bot:password@localhost:5432/bot_scalp_x"
    pool_size: int = 10
    max_overflow: int = 20


class RiskSettings(BaseModel):
    risk_per_trade_pct: float = 0.25
    daily_dd_limit_pct: float = 2.0
    weekly_dd_limit_pct: float = 5.0
    max_consecutive_losses: int = 5
    max_latency_ms: float = 150.0
    max_spread_xauusd: float = 3.0
    max_spread_nas100: float = 5.0
    max_spread_eurusd: float = 1.5

    def max_spread_for(self, symbol: str) -> float:
        return {
            "XAUUSD": self.max_spread_xauusd,
            "NAS100": self.max_spread_nas100,
            "EURUSD": self.max_spread_eurusd,
        }.get(symbol, self.max_spread_eurusd)


class SignalSettings(BaseModel):
    min_votes_required: int = 2
    symbols: list[str] = ["XAUUSD", "NAS100", "EURUSD"]
    ema_fast: int = 9
    ema_slow: int = 21
    momentum_window_fast: int = 5
    momentum_window_slow: int = 20
    atr_period: int = 14
    rsi_period: int = 14


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"
    log_format: str = "json"
    redis_url: str = "redis://:password@localhost:6379/0"

    mt5: MT5Settings = MT5Settings()
    db: DatabaseSettings = DatabaseSettings()
    risk: RiskSettings = RiskSettings()
    signals: SignalSettings = SignalSettings()


_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings
