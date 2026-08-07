async def test_login_success(client):
    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "test-password"}
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


async def test_login_wrong_password(client):
    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "nope"}
    )
    assert resp.status_code == 401


async def test_protected_routes_require_token(client):
    assert (await client.get("/api/leads")).status_code == 401
    assert (await client.get("/api/meetings")).status_code == 401
    assert (
        await client.post("/api/emails/ingest", json={"raw_text": "hi"})
    ).status_code == 401


async def test_garbage_token_rejected(client):
    client.headers["Authorization"] = "Bearer not-a-jwt"
    assert (await client.get("/api/leads")).status_code == 401


async def test_login_rate_limited_after_repeated_failures(client):
    from app.auth import login_limiter

    login_limiter.reset()
    for _ in range(5):
        resp = await client.post(
            "/api/auth/login", json={"email": "admin@test.io", "password": "wrong"}
        )
        assert resp.status_code == 401

    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "wrong"}
    )
    assert resp.status_code == 429

    # Even correct credentials are refused while locked out.
    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "test-password"}
    )
    assert resp.status_code == 429
    login_limiter.reset()


async def test_successful_login_clears_failure_count(client):
    from app.auth import login_limiter

    login_limiter.reset()
    for _ in range(4):
        await client.post("/api/auth/login", json={"email": "admin@test.io", "password": "wrong"})
    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "test-password"}
    )
    assert resp.status_code == 200

    # Counter reset — a single new failure is a 401, not a lockout.
    resp = await client.post(
        "/api/auth/login", json={"email": "admin@test.io", "password": "wrong"}
    )
    assert resp.status_code == 401
    login_limiter.reset()
