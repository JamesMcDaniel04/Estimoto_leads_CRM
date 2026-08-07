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


def test_migration_merges_duplicate_lead_emails(tmp_path):
    """0002 must collapse pre-existing duplicate-email leads (children moved
    to the survivor) before the unique index is created; blank emails stay."""
    from alembic import command

    from app.migrate import _make_config

    db_file = tmp_path / "dupes.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    command.upgrade(_make_config(url), "0001")

    engine = sa.create_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        for name in ("Keep", "Dupe"):
            conn.execute(
                sa.text(
                    "INSERT INTO leads (name, email, phone, company, source, stage, notes,"
                    " created_at, updated_at) VALUES (:n, 'dup@x.com', '', '', 'manual',"
                    " 'new', '', '2026-01-01', '2026-01-01')"
                ),
                {"n": name},
            )
        for n in ("BlankA", "BlankB"):
            conn.execute(
                sa.text(
                    "INSERT INTO leads (name, email, phone, company, source, stage, notes,"
                    " created_at, updated_at) VALUES (:n, '', '', '', 'manual', 'new', '',"
                    " '2026-01-01', '2026-01-01')"
                ),
                {"n": n},
            )
        ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM leads WHERE email='dup@x.com' ORDER BY id"))]
        keep_id, dupe_id = ids
        conn.execute(
            sa.text(
                "INSERT INTO activities (lead_id, type, body, created_at)"
                " VALUES (:lid, 'note', 'on dupe', '2026-01-01')"
            ),
            {"lid": dupe_id},
        )

    run_migrations(url)

    with engine.connect() as conn:
        remaining = [
            r[0] for r in conn.execute(sa.text("SELECT id FROM leads WHERE email='dup@x.com'"))
        ]
        assert remaining == [keep_id]
        moved = conn.execute(
            sa.text("SELECT lead_id FROM activities WHERE body='on dupe'")
        ).scalar_one()
        assert moved == keep_id
        blanks = conn.execute(sa.text("SELECT COUNT(*) FROM leads WHERE email=''")).scalar_one()
        assert blanks == 2

    # The unique index is now enforced for non-blank emails.
    import pytest as _pytest

    with engine.begin() as conn, _pytest.raises(sa.exc.IntegrityError):
        conn.execute(
            sa.text(
                "INSERT INTO leads (name, email, phone, company, source, stage, notes,"
                " created_at, updated_at) VALUES ('X', 'dup@x.com', '', '', 'manual',"
                " 'new', '', '2026-01-01', '2026-01-01')"
            )
        )
    engine.dispose()
