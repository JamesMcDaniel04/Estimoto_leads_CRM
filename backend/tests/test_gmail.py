from app import gmail
from app.config import get_settings
from app.db import SessionLocal
from app.gmail import make_oauth_state, poll_gmail_once, verify_oauth_state
from app.models import GmailAccount


def make_raw(message_id: str, sender: str = "jane@doebodyshop.com") -> bytes:
    return (
        f"From: Jane Doe <{sender}>\r\n"
        f"To: hello@estimoto.io\r\n"
        f"Subject: Demo request\r\n"
        f"Message-ID: <{message_id}>\r\n"
        f"Content-Type: text/plain\r\n\r\n"
        f"We want a demo of Estimoto.\r\n"
    ).encode()


def test_oauth_state_roundtrip():
    assert verify_oauth_state(make_oauth_state()) is True
    assert verify_oauth_state(None) is False
    assert verify_oauth_state("tampered.jwt.value") is False


async def _connect_account(email: str = "hello@estimoto.io") -> None:
    async with SessionLocal() as db:
        db.add(GmailAccount(email=email, refresh_token="rt-test"))
        await db.commit()


def _mock_gmail_api(monkeypatch, messages: dict[str, bytes], marked: list[str]):
    async def fake_refresh(refresh_token):
        return "access-token"

    async def fake_list(token):
        return list(messages)

    async def fake_fetch(token, message_id):
        return messages[message_id]

    async def fake_mark(token, message_id):
        marked.append(message_id)

    monkeypatch.setattr(gmail, "refresh_access_token", fake_refresh)
    monkeypatch.setattr(gmail, "list_unread_ids", fake_list)
    monkeypatch.setattr(gmail, "fetch_raw_message", fake_fetch)
    monkeypatch.setattr(gmail, "mark_read", fake_mark)


async def test_gmail_poll_ingests_and_marks_read(auth_client, monkeypatch):
    await _connect_account()
    marked: list[str] = []
    _mock_gmail_api(monkeypatch, {"gm1": make_raw("gmail-msg-1@test")}, marked)

    await poll_gmail_once()

    assert marked == ["gm1"]
    assert gmail.state["connected"] == ["hello@estimoto.io"]
    assert gmail.state["last_error"] is None

    leads = (await auth_client.get("/api/leads")).json()
    assert len(leads) == 1
    detail = (await auth_client.get(f"/api/leads/{leads[0]['id']}")).json()
    assert detail["emails"][0]["mailbox"] == "hello@estimoto.io"


async def test_gmail_poll_dedupes_on_redelivery(auth_client, monkeypatch):
    await _connect_account()
    marked: list[str] = []
    _mock_gmail_api(monkeypatch, {"gm1": make_raw("gmail-dup@test")}, marked)

    before = gmail.state["ingested_total"]
    await poll_gmail_once()
    await poll_gmail_once()  # e.g. mark_read failed silently upstream

    assert gmail.state["ingested_total"] == before + 1
    leads = (await auth_client.get("/api/leads")).json()
    detail = (await auth_client.get(f"/api/leads/{leads[0]['id']}")).json()
    assert len(detail["emails"]) == 1


async def test_gmail_failed_message_not_marked_read(auth_client, monkeypatch):
    await _connect_account()
    marked: list[str] = []
    _mock_gmail_api(monkeypatch, {"gm1": make_raw("gmail-bad@test")}, marked)

    async def bad_fetch(token, message_id):
        raise ValueError("api hiccup")

    monkeypatch.setattr(gmail, "fetch_raw_message", bad_fetch)

    await poll_gmail_once()

    assert marked == []
    assert gmail.state["last_error"] is not None


async def test_callback_stores_account_and_redirects(auth_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_oauth_client_id", "cid")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "csecret")

    async def fake_exchange(code):
        assert code == "auth-code"
        return {"access_token": "at", "refresh_token": "rt-new"}

    async def fake_profile(token):
        return "hello@estimoto.io"

    import app.routers.gmail as gmail_router

    monkeypatch.setattr(gmail_router, "exchange_code", fake_exchange)
    monkeypatch.setattr(gmail_router, "fetch_profile_email", fake_profile)

    resp = await auth_client.get(
        "/api/gmail/callback",
        params={"code": "auth-code", "state": make_oauth_state()},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].endswith("/inbox?gmail=connected")

    status = (await auth_client.get("/api/gmail/status")).json()
    assert [a["email"] for a in status["connected"]] == ["hello@estimoto.io"]

    # Reconnecting the same mailbox updates the token instead of duplicating.
    resp = await auth_client.get(
        "/api/gmail/callback",
        params={"code": "auth-code", "state": make_oauth_state()},
        follow_redirects=False,
    )
    status = (await auth_client.get("/api/gmail/status")).json()
    assert len(status["connected"]) == 1


async def test_callback_rejects_bad_state(auth_client):
    resp = await auth_client.get(
        "/api/gmail/callback",
        params={"code": "auth-code", "state": "forged"},
        follow_redirects=False,
    )
    assert resp.headers["location"].endswith("/inbox?gmail=error")


async def test_auth_url_requires_configuration(auth_client):
    resp = await auth_client.get("/api/gmail/auth-url")
    assert resp.status_code == 400


async def test_disconnect(auth_client, monkeypatch):
    await _connect_account()

    async def fake_revoke(token):
        pass

    import app.routers.gmail as gmail_router

    monkeypatch.setattr(gmail_router, "revoke_token", fake_revoke)

    status = (await auth_client.get("/api/gmail/status")).json()
    account_id = status["connected"][0]["id"]
    resp = await auth_client.delete(f"/api/gmail/account/{account_id}")
    assert resp.status_code == 204
    status = (await auth_client.get("/api/gmail/status")).json()
    assert status["connected"] == []


def test_oauth_state_is_single_use():
    value = make_oauth_state()
    assert verify_oauth_state(value) is True
    assert verify_oauth_state(value) is False  # replay must fail
