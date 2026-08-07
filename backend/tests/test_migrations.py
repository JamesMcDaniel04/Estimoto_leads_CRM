"""Schema is managed by Alembic. Two paths matter:

1. Fresh database → migrations build the full schema from nothing.
2. Legacy database (created by the old ``create_all`` startup, so it has
   tables but no ``alembic_version``) → adopted by stamping the baseline
   revision instead of failing on "table already exists".
"""

import sqlalchemy as sa

from app.db import Base
from app.migrate import run_migrations

EXPECTED_TABLES = {"leads", "email_messages", "meetings", "activities", "gmail_accounts"}


def _table_names(sync_url: str) -> set[str]:
    engine = sa.create_engine(sync_url)
    try:
        with engine.connect() as conn:
            return set(sa.inspect(conn).get_table_names())
    finally:
        engine.dispose()


def test_migrations_build_schema_on_fresh_db(tmp_path):
    db_file = tmp_path / "fresh.db"
    run_migrations(f"sqlite+aiosqlite:///{db_file}")

    tables = _table_names(f"sqlite:///{db_file}")
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables


def test_migrations_adopt_legacy_create_all_db(tmp_path):
    db_file = tmp_path / "legacy.db"
    sync_url = f"sqlite:///{db_file}"
    engine = sa.create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    # Must not raise "table already exists" — stamps baseline, then upgrades.
    run_migrations(f"sqlite+aiosqlite:///{db_file}")

    tables = _table_names(sync_url)
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables


def test_migrations_are_idempotent(tmp_path):
    db_file = tmp_path / "twice.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    run_migrations(url)
    run_migrations(url)

    assert EXPECTED_TABLES <= _table_names(f"sqlite:///{db_file}")


async def test_init_db_migrates_file_backed_database(tmp_path, monkeypatch):
    """Startup runs migrations (not create_all) for real databases."""
    from app import db as db_module
    from app.config import Settings

    db_file = tmp_path / "startup.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setattr(db_module, "get_settings", lambda: Settings(database_url=url))

    await db_module.init_db()

    tables = _table_names(f"sqlite:///{db_file}")
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables
