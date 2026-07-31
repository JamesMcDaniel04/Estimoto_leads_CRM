from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./crm.db"
    jwt_secret: str = "change-me-in-production"
    jwt_ttl_hours: int = 24 * 7

    admin_email: str = "admin@estimoto.io"
    admin_password: str = "change-me"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
