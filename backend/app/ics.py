"""Minimal RFC 5545 .ics generation for meeting invites."""

from datetime import datetime, timezone

from .models import Meeting


def _fmt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def meeting_to_ics(meeting: Meeting, attendee_email: str = "") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Estimoto//Leads CRM//EN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:estimoto-crm-meeting-{meeting.id}@estimoto.io",
        f"DTSTAMP:{_fmt(meeting.created_at)}",
        f"DTSTART:{_fmt(meeting.starts_at)}",
        f"DTEND:{_fmt(meeting.ends_at)}",
        f"SUMMARY:{_escape(meeting.title)}",
    ]
    if meeting.location:
        lines.append(f"LOCATION:{_escape(meeting.location)}")
    if meeting.notes:
        lines.append(f"DESCRIPTION:{_escape(meeting.notes)}")
    if attendee_email:
        lines.append(f"ATTENDEE;RSVP=TRUE:mailto:{attendee_email}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"
