from app import imap_poller
from app.imap_poller import ImapAccount, load_accounts, poll_once

ACCOUNT = ImapAccount(email="hello@estimoto.io", password="x", host="imap.test")


def make_raw(message_id: str, sender: str = "jane@doebodyshop.com") -> bytes:
    return (
        f"From: Jane Doe <{sender}>\r\n"
        f"To: hello@estimoto.io\r\n"
        f"Subject: Demo request\r\n"
        f"Message-ID: <{message_id}>\r\n"
        f"Content-Type: text/plain\r\n\r\n"
        f"We want a demo of Estimoto.\r\n"
    ).encode()


async def test_poll_ingests_and_marks_seen(auth_client, monkeypatch):
    seen: list[bytes] = []
    monkeypatch.setattr(
        imap_poller, "fetch_unseen", lambda acct: [(b"101", make_raw("msg-1@test"))]
    )
    monkeypatch.setattr(imap_poller, "mark_seen", lambda acct, uids: seen.extend(uids))

    await poll_once([ACCOUNT])

    assert seen == [b"101"]
    assert imap_poller.state["last_error"] is None
    assert imap_poller.state["mailboxes"] == ["hello@estimoto.io"]

    leads = (await auth_client.get("/api/leads")).json()
    assert len(leads) == 1
    assert leads[0]["email"] == "jane@doebodyshop.com"
    detail = (await auth_client.get(f"/api/leads/{leads[0]['id']}")).json()
    assert detail["emails"][0]["mailbox"] == "hello@estimoto.io"


async def test_poll_dedupes_by_message_id(auth_client, monkeypatch):
    monkeypatch.setattr(
        imap_poller, "fetch_unseen", lambda acct: [(b"101", make_raw("msg-dup@test"))]
    )
    monkeypatch.setattr(imap_poller, "mark_seen", lambda acct, uids: None)

    before = imap_poller.state["ingested_total"]
    await poll_once([ACCOUNT])
    await poll_once([ACCOUNT])  # same message redelivered (e.g. mark_seen failed)

    assert imap_poller.state["ingested_total"] == before + 1
    leads = (await auth_client.get("/api/leads")).json()
    detail = (await auth_client.get(f"/api/leads/{leads[0]['id']}")).json()
    assert len(detail["emails"]) == 1


async def test_poll_multiple_accounts_isolated_failure(auth_client, monkeypatch):
    """One broken mailbox must not block the other."""
    good = ImapAccount(email="estimates@estimoto.io", password="x", host="imap.test")

    def fake_fetch(acct):
        if acct.email == "hello@estimoto.io":
            raise ConnectionError("login failed")
        return [(b"7", make_raw("msg-2@test", sender="bob@smithauto.com"))]

    monkeypatch.setattr(imap_poller, "fetch_unseen", fake_fetch)
    monkeypatch.setattr(imap_poller, "mark_seen", lambda acct, uids: None)

    await poll_once([ACCOUNT, good])

    assert "hello@estimoto.io" in imap_poller.state["last_error"]
    leads = (await auth_client.get("/api/leads")).json()
    assert any(l["email"] == "bob@smithauto.com" for l in leads)


async def test_failed_message_not_marked_seen(auth_client, monkeypatch):
    """A message that fails to parse stays unseen for retry; others proceed."""
    seen: list[bytes] = []

    def bad_parse(raw):
        raise ValueError("corrupt message")

    monkeypatch.setattr(imap_poller, "parse_eml", bad_parse)
    monkeypatch.setattr(
        imap_poller, "fetch_unseen", lambda acct: [(b"9", make_raw("msg-3@test"))]
    )
    monkeypatch.setattr(imap_poller, "mark_seen", lambda acct, uids: seen.extend(uids))

    await poll_once([ACCOUNT])

    assert seen == []
    assert imap_poller.state["last_error"] is not None


def test_load_accounts_parsing(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "imap_accounts",
        '[{"email": "hello@estimoto.io", "password": "a"},'
        ' {"email": "estimates@estimoto.io", "password": "b", "host": "mail.other.io"}]',
    )
    accounts = load_accounts()
    assert [a.email for a in accounts] == ["hello@estimoto.io", "estimates@estimoto.io"]
    assert accounts[0].host == settings.imap_host
    assert accounts[1].host == "mail.other.io"

    monkeypatch.setattr(settings, "imap_accounts", "not json")
    try:
        load_accounts()
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    monkeypatch.setattr(settings, "imap_accounts", "")
    assert load_accounts() == []
