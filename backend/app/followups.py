"""Follow-up engine: decide which leads need attention and why.

Pure rules over lead state — instant, deterministic, and works with no AI
key. Priorities: 1 = act today, 2 = due, 3 = getting stale.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import Lead


@dataclass
class FollowUp:
    lead: Lead
    reason: str
    priority: int
    days_idle: int


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; everything we store is UTC.
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _last_touch(lead: Lead) -> datetime:
    latest = lead.created_at
    for activity in lead.activities:
        if activity.created_at > latest:
            latest = activity.created_at
    return latest


def compute_followup(lead: Lead, now: datetime | None = None) -> FollowUp | None:
    now = now or datetime.now(timezone.utc)
    if lead.stage in ("won", "lost"):
        return None

    last_touch = _aware(_last_touch(lead))
    days_idle = max(0, (now - last_touch).days)

    if lead.stage == "meeting_scheduled":
        past_meetings = [m for m in lead.meetings if _aware(m.ends_at) < now]
        if past_meetings:
            latest_end = max(_aware(m.ends_at) for m in past_meetings)
            touched_since = last_touch > latest_end
            if not touched_since:
                return FollowUp(
                    lead, "Meeting happened — send recap and next steps", 1, days_idle
                )
        if days_idle >= 7:
            return FollowUp(lead, f"No touch in {days_idle} days despite scheduled meeting", 3, days_idle)
        return None

    if lead.stage == "new" and days_idle >= 1:
        return FollowUp(lead, f"New lead awaiting first contact for {days_idle} day{'s' if days_idle != 1 else ''}", 1, days_idle)

    if lead.stage in ("contacted", "qualified") and days_idle >= 3:
        return FollowUp(lead, f"Gone quiet — no activity in {days_idle} days", 2, days_idle)

    if lead.stage == "proposal" and days_idle >= 5:
        return FollowUp(lead, f"Proposal outstanding {days_idle} days without follow-up", 1, days_idle)

    return None


def compute_followups(leads: list[Lead], now: datetime | None = None) -> list[FollowUp]:
    now = now or datetime.now(timezone.utc)
    results = [f for lead in leads if (f := compute_followup(lead, now))]
    results.sort(key=lambda f: (f.priority, -f.days_idle))
    return results
