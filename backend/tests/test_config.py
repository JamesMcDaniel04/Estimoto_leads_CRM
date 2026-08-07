"""Production deploys must never boot with the insecure placeholder secrets."""

import pytest

from app.config import Settings


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            app_env="production",
            jwt_secret="change-me-in-production",
            admin_password="a-real-password",
        )


def test_production_rejects_default_admin_password():
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings(
            app_env="production",
            jwt_secret="a-real-secret",
            admin_password="change-me",
        )


def test_production_rejects_empty_secrets():
    with pytest.raises(ValueError):
        Settings(app_env="production", jwt_secret="", admin_password="")


def test_production_boots_with_real_secrets():
    s = Settings(
        app_env="production",
        jwt_secret="a-real-secret",
        admin_password="a-real-password",
    )
    assert s.app_env == "production"


def test_development_allows_placeholder_defaults():
    s = Settings(
        app_env="development",
        jwt_secret="change-me-in-production",
        admin_password="change-me",
    )
    assert s.jwt_secret == "change-me-in-production"
