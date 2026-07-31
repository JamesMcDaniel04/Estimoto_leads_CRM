async def _make_lead(auth_client, **kw):
    payload = {"name": "Jane", "email": "jane@shop.com", **kw}
    return (await auth_client.post("/api/leads", json=payload)).json()


async def test_create_meeting_advances_stage_and_logs(auth_client):
    lead = await _make_lead(auth_client)
    resp = await auth_client.post(
        "/api/meetings",
        json={
            "lead_id": lead["id"],
            "title": "Estimoto demo",
            "starts_at": "2026-08-05T15:00:00Z",
            "ends_at": "2026-08-05T15:30:00Z",
            "location": "https://meet.example.com/demo",
        },
    )
    assert resp.status_code == 201

    detail = (await auth_client.get(f"/api/leads/{lead['id']}")).json()
    assert detail["stage"] == "meeting_scheduled"
    assert any(a["type"] == "meeting_scheduled" for a in detail["activities"])


async def test_meeting_does_not_regress_late_stage(auth_client):
    lead = await _make_lead(auth_client, stage="proposal")
    await auth_client.post(
        "/api/meetings",
        json={
            "lead_id": lead["id"],
            "title": "Follow-up",
            "starts_at": "2026-08-05T15:00:00Z",
            "ends_at": "2026-08-05T16:00:00Z",
        },
    )
    detail = (await auth_client.get(f"/api/leads/{lead['id']}")).json()
    assert detail["stage"] == "proposal"


async def test_meeting_time_validation(auth_client):
    lead = await _make_lead(auth_client)
    resp = await auth_client.post(
        "/api/meetings",
        json={
            "lead_id": lead["id"],
            "title": "Bad",
            "starts_at": "2026-08-05T15:00:00Z",
            "ends_at": "2026-08-05T14:00:00Z",
        },
    )
    assert resp.status_code == 422


async def test_ics_download(auth_client):
    lead = await _make_lead(auth_client)
    meeting = (
        await auth_client.post(
            "/api/meetings",
            json={
                "lead_id": lead["id"],
                "title": "Demo; with, specials",
                "starts_at": "2026-08-05T15:00:00Z",
                "ends_at": "2026-08-05T15:30:00Z",
                "location": "Zoom",
            },
        )
    ).json()

    resp = await auth_client.get(f"/api/meetings/{meeting['id']}/ics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    body = resp.text
    assert "BEGIN:VCALENDAR" in body
    assert "DTSTART:20260805T150000Z" in body
    assert "SUMMARY:Demo\\; with\\, specials" in body
    assert "mailto:jane@shop.com" in body
