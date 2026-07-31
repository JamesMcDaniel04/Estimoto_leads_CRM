"""Claude-powered next-step suggestions for a lead."""

from .config import get_settings
from .models import Lead


def ai_enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def _lead_context(lead: Lead) -> str:
    lines = [
        f"Lead: {lead.name or 'unknown'} <{lead.email}> — company: {lead.company or 'unknown'}",
        f"Stage: {lead.stage} · source: {lead.source} · est. value: {lead.estimated_value or 'unknown'}",
        f"Notes: {lead.notes[:500]}" if lead.notes else "",
        "",
        "Recent emails:",
    ]
    for em in lead.emails[-3:]:
        lines.append(f"- [{em.received_at:%Y-%m-%d}] {em.subject or '(no subject)'}: {em.raw_body[:800]}")
    if not lead.emails:
        lines.append("- none on file")
    lines.append("")
    lines.append("Activity (newest first):")
    for act in lead.activities[:10]:
        lines.append(f"- [{act.created_at:%Y-%m-%d}] {act.type}: {act.body[:200]}")
    if lead.meetings:
        lines.append("")
        lines.append("Meetings:")
        for m in lead.meetings:
            lines.append(f"- {m.title} at {m.starts_at:%Y-%m-%d %H:%M} ({m.location or 'no location'})")
    return "\n".join(line for line in lines if line is not None)


def suggest_next_action(lead: Lead) -> str:
    """One short, concrete recommendation. Raises on API failure —
    callers surface the error rather than fake a suggestion."""
    import anthropic

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=300,
        system=(
            "You are a sales assistant for Estimoto, an AI estimating tool for "
            "auto-body/collision shops. Given one lead's history, recommend the "
            "single best next action to move the deal forward. Be specific and "
            "brief: 2-3 sentences, imperative voice, reference actual details "
            "from their emails when useful. No preamble."
        ),
        messages=[{"role": "user", "content": _lead_context(lead)}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
