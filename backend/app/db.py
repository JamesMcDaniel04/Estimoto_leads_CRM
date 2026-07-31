from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    # In-memory SQLite needs a single shared connection or every pooled
    # connection sees its own empty database (used by the test suite).
    if url.endswith(":memory:") or url in ("sqlite+aiosqlite://", "sqlite://"):
        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return {}


_url = get_settings().database_url
engine = create_async_engine(_url, echo=False, **_engine_kwargs(_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
