"""AI calls use the synchronous Anthropic client; they must run in a worker
thread so a slow API call never stalls the event loop (and with it the
mail poller and every other request)."""

import threading

from app import ingest as ingest_module
from app.extraction import Extraction
from app.routers import followups as followups_router


async def test_ingest_extraction_runs_off_event_loop(auth_client, monkeypatch):
    loop_thread = threading.get_ident()
    seen = {}

    def fake_extract(parsed):
        seen["thread"] = threading.get_ident()
        return Extraction(name="Jane", email="jane@shop.com", intent="demo", method="claude")

    monkeypatch.setattr(ingest_module, "extract", fake_extract)

    resp = await auth_client.post(
        "/api/emails/ingest",
        json={"raw_text": "From: Jane <jane@shop.com>\nSubject: Demo\n\nHi there"},
    )

    assert resp.status_code == 200
    assert resp.json()["extraction_method"] == "claude"
    assert seen["thread"] != loop_thread


async def test_suggest_next_runs_off_event_loop(auth_client, monkeypatch):
    loop_thread = threading.get_ident()
    seen = {}

    def fake_suggest(lead):
        seen["thread"] = threading.get_ident()
        return "Call them back today."

    monkeypatch.setattr(followups_router, "ai_enabled", lambda: True)
    monkeypatch.setattr(followups_router, "suggest_next_action", fake_suggest)

    lead_resp = await auth_client.post(
        "/api/leads", json={"name": "Amy", "email": "amy@garage.com"}
    )
    assert lead_resp.status_code == 201
    lead_id = lead_resp.json()["id"]

    resp = await auth_client.post(f"/api/leads/{lead_id}/suggest-next")

    assert resp.status_code == 200
    assert resp.json()["suggestion"] == "Call them back today."
    assert seen["thread"] != loop_thread
