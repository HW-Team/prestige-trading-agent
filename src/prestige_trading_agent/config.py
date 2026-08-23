from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PRESTIGE_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./prestige.db"
    admin_api_key: SecretStr = SecretStr("change-me")
    meta_verify_token: SecretStr = SecretStr("change-me")
    meta_app_secret: SecretStr = SecretStr("change-me")
    meta_page_access_token: SecretStr | None = None
    form_webhook_secret: SecretStr = SecretStr("change-me")
    stripe_webhook_secret: SecretStr = SecretStr("change-me")
    model: str = "test"
    model_base_url: str | None = None
    model_api_key: SecretStr | None = None
    outbound_mode: Literal["recording", "live"] = "recording"
    free_line_invite_url: str = "https://lin.ee/WcilwHP"
    newbie_form_url: str = (
        "https://www.bravotradeacademy.com/course/daily-cash-flow-trading-system/"
    )
    course_checkout_url: str = "https://lin.ee/WcilwHP"
    indicator_form_url: str = "https://lin.ee/WcilwHP"
    lms_endpoint: str | None = "https://classroom.bravotradeacademy.com/courses/dcts/"
    lms_api_key: SecretStr | None = None
    support_line_oa: str = "@prestigeclub"
    privacy_policy_url: str = "https://www.bravotradeacademy.com/privacy-policy"
    terms_of_service_url: str = "https://www.bravotradeacademy.com/terms-of-service"
    # Optional: push tester feedback to a Telegram chat (e.g. the HW Team
    # channel) the moment it is captured, so the agent operator can act on it.
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
