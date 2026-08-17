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
    outbound_mode: Literal["recording", "live"] = "recording"
    free_line_invite_url: str = "https://line.me/R/ti/g/configure-me"
    newbie_form_url: str = "https://example.com/newbie"
    course_checkout_url: str = "https://example.com/course"
    indicator_form_url: str = "https://example.com/indicator"
    lms_endpoint: str | None = None
    lms_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
