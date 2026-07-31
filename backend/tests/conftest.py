import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@test.io"
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import init_db, engine, Base
from app.main import app


@pytest_asyncio.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def auth_client(client):
    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "test-password"}
    )
    client.headers["Authorization"] = f"Bearer {resp.json()['token']}"
    return client


@pytest.fixture
def anyio_backend():
    return "asyncio"
