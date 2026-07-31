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

    # IMAP auto-ingestion. IMAP_ACCOUNTS is a JSON list, e.g.
    # [{"email": "hello@estimoto.io", "password": "app-password"},
    #  {"email": "estimates@estimoto.io", "password": "app-password"}]
    # Host/port default to imap_host/imap_port unless set per account.
    imap_accounts: str = ""
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_poll_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
