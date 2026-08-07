from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_JWT_SECRET = "change-me-in-production"
INSECURE_ADMIN_PASSWORD = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "production" (set via APP_ENV in fly.toml) refuses to boot with the
    # placeholder secrets below; anything else is treated as development.
    app_env: str = "development"

    database_url: str = "sqlite+aiosqlite:///./crm.db"
    jwt_secret: str = INSECURE_JWT_SECRET
    jwt_ttl_hours: int = 24 * 7

    admin_email: str = "admin@estimoto.io"
    admin_password: str = INSECURE_ADMIN_PASSWORD

    @model_validator(mode="after")
    def _require_real_secrets_in_production(self) -> "Settings":
        if self.app_env != "production":
            return self
        problems = []
        if not self.jwt_secret or self.jwt_secret == INSECURE_JWT_SECRET:
            problems.append("JWT_SECRET")
        if not self.admin_password or self.admin_password == INSECURE_ADMIN_PASSWORD:
            problems.append("ADMIN_PASSWORD")
        if problems:
            raise ValueError(
                f"APP_ENV=production but {', '.join(problems)} unset or left at the "
                "insecure default — set real values (fly secrets set ...) before deploying"
            )
        return self

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    cors_origins: str = "http://localhost:5173"

    # Native Gmail integration (preferred): reuses the Estimoto Google OAuth
    # client — same env names as the product backend. The redirect URL must
    # be registered on that OAuth client in Google Cloud console.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_url: str = "http://localhost:8000/api/gmail/callback"
    frontend_url: str = "http://localhost:5173"

    # IMAP auto-ingestion (fallback, app-password based). IMAP_ACCOUNTS is a JSON list, e.g.
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
