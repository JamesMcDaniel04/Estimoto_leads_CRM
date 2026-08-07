"""Run Alembic migrations programmatically at startup.

Synchronous by design — the async env.py calls ``asyncio.run`` internally,
so this must execute in a worker thread (``asyncio.to_thread``), never on
the event loop itself.
"""

import asyncio
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0001"


def _make_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["sqlalchemy_url"] = url
    return cfg


def _needs_baseline_stamp(url: str) -> bool:
    """A database created by the old ``create_all`` startup has our tables
    but no ``alembic_version`` — it must be stamped, not re-created."""

    async def check() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                tables = await conn.run_sync(
                    lambda sync_conn: set(sa.inspect(sync_conn).get_table_names())
                )
        finally:
            await engine.dispose()
        return "leads" in tables and "alembic_version" not in tables

    return asyncio.run(check())


def run_migrations(url: str) -> None:
    cfg = _make_config(url)
    if _needs_baseline_stamp(url):
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
