"""
Central configuration. Every secret/setting comes from environment variables.
Never hardcode tokens or credentials here.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-prod"
    ADMIN_API_TOKEN: str = "change-me-admin-token"

    # --- Telegram ---
    BOT_TOKEN: str = ""
    BOT_WEBHOOK_SECRET: str = "change-me-webhook-secret"
    BOT_WEBHOOK_URL: Optional[str] = None  # e.g. https://yourdomain.com/webhook/telegram
    BOT_USE_WEBHOOK: bool = False  # False => long polling (good for local dev)
    ADMIN_TG_IDS: str = ""  # comma-separated telegram user ids with admin rights
    ADMIN_API_TOKEN: str = "change-me-admin-api-token"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://livematch:livematch@db:5432/livematch"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Payments ---
    TELEGRAM_PAYMENTS_PROVIDER_TOKEN: str = ""  # empty = Stars (XTR), no provider token needed
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    LIQPAY_PUBLIC_KEY: str = ""
    LIQPAY_PRIVATE_KEY: str = ""
    FONDY_MERCHANT_ID: str = ""
    FONDY_SECRET_KEY: str = ""
    WAYFORPAY_MERCHANT_ACCOUNT: str = ""
    WAYFORPAY_SECRET_KEY: str = ""

    # --- AI module ---
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"

    # --- Web app ---
    WEBAPP_BASE_URL: str = "http://localhost:8080"
    API_BASE_URL: str = "http://localhost:8000"

    # --- Limits (business rules) ---
    FREE_LIKES_PER_DAY: int = 15
    INCOMING_LIKES_SOFT_LIMIT: int = 20          # per INCOMING_LIMIT_WINDOW_HOURS
    INCOMING_LIMIT_WINDOW_HOURS: int = 24
    ACTIVE_CHAT_TTL_HOURS: int = 24
    CHAT_INACTIVITY_AUTOCLOSE_HOURS: int = 12
    MAX_CHAT_EXTENSIONS: int = 10
    MESSAGES_PER_MINUTE_LIMIT: int = 20
    IDENTICAL_MESSAGE_LIMIT: int = 3
    REFERRAL_INVITER_BONUS_LIKES: int = 5
    REFERRAL_INVITED_BONUS_LIKES: int = 5
    DEFAULT_SEARCH_RADIUS_KM: int = 15
    RUN_SCHEDULER_IN_API: bool = True  # set False when a separate `worker` process/container handles it

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.ADMIN_TG_IDS.split(",") if x.strip().isdigit()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
