from datetime import datetime, timedelta, timezone

from app.followups import compute_followup, compute_followups
from app.models import Activity, Lead, Meeting

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


def make_lead(stage="new", created_days_ago=0, last_activity_days_ago=None, **kw) -> Lead:
    lead = Lead(stage=stage, name="Test", email="t@x.com", **kw)
    lead.created_at = NOW - timedelta(days=created_days_ago)
    lead.activities = []
    lead.meetings = []
    if last_activity_days_ago is not None:
        act = Activity(type="note", body="touched")
        act.created_at = NOW - timedelta(days=last_activity_days_ago)
        lead.activities.append(act)
    return lead


def test_fresh_new_lead_not_flagged():
    assert compute_followup(make_lead("new", created_days_ago=0), NOW) is None


def test_new_lead_awaiting_first_contact():
    f = compute_followup(make_lead("new", created_days_ago=2), NOW)
    assert f is not None and f.priority == 1
    assert "first contact" in f.reason


def test_contacted_gone_quiet():
    f = compute_followup(make_lead("contacted", created_days_ago=10, last_activity_days_ago=4), NOW)
    assert f is not None and f.priority == 2
    assert f.days_idle == 4


def test_recent_activity_suppresses_flag():
    assert (
        compute_followup(make_lead("contacted", created_days_ago=10, last_activity_days_ago=1), NOW)
        is None
    )


def test_meeting_passed_needs_recap():
    lead = make_lead("meeting_scheduled", created_days_ago=5, last_activity_days_ago=3)
    meeting = Meeting(title="Demo", starts_at=NOW - timedelta(days=2), ends_at=NOW - timedelta(days=2))
    lead.meetings.append(meeting)
    f = compute_followup(lead, NOW)
    assert f is not None and f.priority == 1
    assert "recap" in f.reason


def test_meeting_passed_but_already_followed_up():
    lead = make_lead("meeting_scheduled", created_days_ago=5, last_activity_days_ago=1)
    meeting = Meeting(title="Demo", starts_at=NOW - timedelta(days=2), ends_at=NOW - timedelta(days=2))
    lead.meetings.append(meeting)
    assert compute_followup(lead, NOW) is None


def test_proposal_outstanding():
    f = compute_followup(make_lead("proposal", created_days_ago=20, last_activity_days_ago=6), NOW)
    assert f is not None and f.priority == 1


def test_won_lost_never_flagged():
    assert compute_followup(make_lead("won", created_days_ago=30), NOW) is None
    assert compute_followup(make_lead("lost", created_days_ago=30), NOW) is None


def test_sorting_priority_then_staleness():
    leads = [
        make_lead("contacted", created_days_ago=10, last_activity_days_ago=4),  # p2
        make_lead("new", created_days_ago=3),  # p1, 3d
        make_lead("new", created_days_ago=9),  # p1, 9d
    ]
    result = compute_followups(leads, NOW)
    assert [(f.priority, f.days_idle) for f in result] == [(1, 9), (1, 3), (2, 4)]


async def test_followups_endpoint_and_integrations(auth_client):
    await auth_client.post("/api/leads", json={"name": "Fresh", "email": "f@x.com"})
    resp = await auth_client.get("/api/followups")
    assert resp.status_code == 200
    assert resp.json() == []  # brand-new lead, not yet due

    resp = await auth_client.get("/api/integrations")
    body = resp.json()
    assert body["ai_extraction"] is False
    assert body["gmail"]["configured"] is False
    assert body["gmail"]["connected"] == []


async def test_suggest_next_requires_ai(auth_client):
    lead_id = (await auth_client.post("/api/leads", json={"name": "X"})).json()["id"]
    resp = await auth_client.post(f"/api/leads/{lead_id}/suggest-next")
    assert resp.status_code == 400
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]
