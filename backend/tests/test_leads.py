async def test_create_and_list_leads(auth_client):
    resp = await auth_client.post(
        "/api/leads",
        json={"name": "Jane", "email": "jane@shop.com", "company": "Shop Co"},
    )
    assert resp.status_code == 201
    lead = resp.json()
    assert lead["stage"] == "new"

    resp = await auth_client.get("/api/leads")
    assert [l["id"] for l in resp.json()] == [lead["id"]]


async def test_stage_change_logs_activity(auth_client):
    lead_id = (
        await auth_client.post("/api/leads", json={"name": "Jane", "email": "j@x.com"})
    ).json()["id"]

    resp = await auth_client.patch(f"/api/leads/{lead_id}", json={"stage": "contacted"})
    assert resp.status_code == 200
    assert resp.json()["stage"] == "contacted"

    detail = (await auth_client.get(f"/api/leads/{lead_id}")).json()
    types = [a["type"] for a in detail["activities"]]
    assert "stage_changed" in types and "created" in types


async def test_invalid_stage_rejected(auth_client):
    lead_id = (await auth_client.post("/api/leads", json={"name": "X"})).json()["id"]
    resp = await auth_client.patch(f"/api/leads/{lead_id}", json={"stage": "bogus"})
    assert resp.status_code == 422


async def test_notes_and_delete(auth_client):
    lead_id = (await auth_client.post("/api/leads", json={"name": "X"})).json()["id"]
    resp = await auth_client.post(f"/api/leads/{lead_id}/notes", json={"body": "called them"})
    assert resp.status_code == 201

    assert (await auth_client.delete(f"/api/leads/{lead_id}")).status_code == 204
    assert (await auth_client.get(f"/api/leads/{lead_id}")).status_code == 404


async def test_ingest_creates_then_matches_lead(auth_client):
    email_text = (
        "From: Jane Doe <jane@doebodyshop.com>\n"
        "Subject: Demo please\n\n"
        "We'd like a demo. Call (555) 123-4567."
    )
    resp = await auth_client.post("/api/emails/ingest", json={"raw_text": email_text})
    assert resp.status_code == 200
    body = resp.json()
    assert body["lead_created"] is True
    assert body["extraction_method"] == "fallback"
    assert body["lead"]["email"] == "jane@doebodyshop.com"
    assert body["lead"]["source"] == "inbound_email"
    lead_id = body["lead"]["id"]

    # Second email from the same sender attaches to the existing lead.
    resp = await auth_client.post(
        "/api/emails/ingest",
        json={"raw_text": "From: jane@doebodyshop.com\nSubject: Following up\n\nAny update?"},
    )
    assert resp.json()["lead_created"] is False
    assert resp.json()["lead"]["id"] == lead_id

    detail = (await auth_client.get(f"/api/leads/{lead_id}")).json()
    assert len(detail["emails"]) == 2
    assert sum(1 for a in detail["activities"] if a["type"] == "email_ingested") == 2


async def test_leads_pagination(auth_client):
    for i in range(3):
        await auth_client.post("/api/leads", json={"name": f"Lead {i}", "email": f"l{i}@x.com"})

    assert len((await auth_client.get("/api/leads")).json()) == 3

    page1 = (await auth_client.get("/api/leads?limit=2")).json()
    page2 = (await auth_client.get("/api/leads?limit=2&offset=2")).json()
    assert len(page1) == 2
    assert len(page2) == 1
    assert {l["id"] for l in page1}.isdisjoint({l["id"] for l in page2})


async def test_duplicate_nonblank_email_rejected_with_409(auth_client):
    first = await auth_client.post("/api/leads", json={"name": "A", "email": "same@x.com"})
    assert first.status_code == 201

    dup = await auth_client.post("/api/leads", json={"name": "B", "email": "same@x.com"})
    assert dup.status_code == 409

    # Patching a lead onto an email already in use is also a conflict.
    other = await auth_client.post("/api/leads", json={"name": "C", "email": "other@x.com"})
    resp = await auth_client.patch(
        f"/api/leads/{other.json()['id']}", json={"email": "same@x.com"}
    )
    assert resp.status_code == 409


async def test_blank_emails_do_not_conflict(auth_client):
    assert (await auth_client.post("/api/leads", json={"name": "A"})).status_code == 201
    assert (await auth_client.post("/api/leads", json={"name": "B"})).status_code == 201


async def test_ingest_race_on_same_sender_attaches_to_one_lead(auth_client, monkeypatch):
    """If another writer creates the lead between our lookup and commit, the
    unique index fires and ingestion must retry against the existing lead."""
    from app import ingest as ingest_module

    first = await auth_client.post(
        "/api/emails/ingest",
        json={"raw_text": "From: Jane <jane@shop.com>\nSubject: One\n\nhi"},
    )
    lead_id = first.json()["lead"]["id"]

    real_find = ingest_module._find_lead
    calls = {"n": 0}

    async def stale_miss(db, email):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # simulate the racing lookup that ran before the other commit
        return await real_find(db, email)

    monkeypatch.setattr(ingest_module, "_find_lead", stale_miss)

    resp = await auth_client.post(
        "/api/emails/ingest",
        json={"raw_text": "From: Jane <jane@shop.com>\nSubject: Two\n\nhi again"},
    )
    assert resp.status_code == 200
    assert resp.json()["lead_created"] is False
    assert resp.json()["lead"]["id"] == lead_id
    assert calls["n"] >= 2
