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
