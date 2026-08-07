import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _is_memory_url(url: str) -> bool:
    return url.endswith(":memory:") or url in ("sqlite+aiosqlite://", "sqlite://")


def _engine_kwargs(url: str) -> dict:
    # In-memory SQLite needs a single shared connection or every pooled
    # connection sees its own empty database (used by the test suite).
    if _is_memory_url(url):
        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return {}


_url = get_settings().database_url
engine = create_async_engine(_url, echo=False, **_engine_kwargs(_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    url = get_settings().database_url
    if _is_memory_url(url):
        # Alembic opens its own connection, which for in-memory SQLite would
        # be a separate empty database — so tests keep create_all.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return
    from .migrate import run_migrations

    # run_migrations calls asyncio.run internally; it must run off-loop.
    await asyncio.to_thread(run_migrations, url)
