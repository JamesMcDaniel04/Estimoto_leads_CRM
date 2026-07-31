"""Turn an inbound email into structured lead fields.

Claude does the extraction when an API key is configured; a deterministic
header/regex fallback keeps ingestion working without one. Extraction must
never block ingestion — any Claude failure degrades to the fallback.
"""

import email
import email.policy
import json
import re
from dataclasses import asdict, dataclass, field

from .config import get_settings

EXTRACTION_TOOL = {
    "name": "record_lead",
    "description": "Record structured sales-lead information extracted from an inbound email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Sender's full name"},
            "email": {"type": "string", "description": "Sender's email address"},
            "phone": {"type": "string", "description": "Phone number if mentioned"},
            "company": {"type": "string", "description": "Company or shop name"},
            "intent": {
                "type": "string",
                "description": "One-sentence summary of what the customer wants",
            },
            "estimated_value": {
                "type": "number",
                "description": "Deal value in USD if any budget/size signal exists, else omit",
            },
        },
        "required": ["name", "email", "intent"],
    },
}


@dataclass
class ParsedEmail:
    sender_name: str = ""
    sender_email: str = ""
    subject: str = ""
    body: str = ""
    message_id: str = ""


@dataclass
class Extraction:
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    intent: str = ""
    estimated_value: float | None = None
    method: str = "fallback"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


# Regex scans are bounded to this many chars — inbound mail is untrusted and
# unattended (IMAP poller), so pathological bodies must not cause slow scans.
MAX_SCAN = 20_000

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Matches US-style phone numbers with enough digits to be real (avoids dates/zips).
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
FROM_LINE_RE = re.compile(r"^from:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def parse_eml(raw: bytes) -> ParsedEmail:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    body = ""
    if msg.is_multipart():
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is not None:
            body = part.get_content()
    else:
        body = msg.get_content()
    name, addr = email.utils.parseaddr(msg.get("From", ""))
    return ParsedEmail(
        sender_name=name,
        sender_email=addr,
        subject=msg.get("Subject", ""),
        body=body.strip(),
        message_id=(msg.get("Message-ID") or "").strip(),
    )


def parse_pasted(text: str) -> ParsedEmail:
    """Best-effort parse of a pasted email (may include From:/Subject: lines)."""
    parsed = ParsedEmail(body=text.strip())
    scan = text[:MAX_SCAN]
    from_match = FROM_LINE_RE.search(scan)
    if from_match:
        name, addr = email.utils.parseaddr(from_match.group(1).strip())
        parsed.sender_name = name
        parsed.sender_email = addr
    if not parsed.sender_email:
        first_email = EMAIL_RE.search(scan)
        if first_email:
            parsed.sender_email = first_email.group(0)
    subj_match = re.search(r"^subject:\s*(.*)$", scan, re.IGNORECASE | re.MULTILINE)
    if subj_match:
        parsed.subject = subj_match.group(1).strip()
    return parsed


def fallback_extract(parsed: ParsedEmail) -> Extraction:
    ex = Extraction(method="fallback")
    ex.name = parsed.sender_name
    ex.email = parsed.sender_email
    phone = PHONE_RE.search(parsed.body[:MAX_SCAN])
    if phone:
        ex.phone = phone.group(0).strip()
    if not ex.name and parsed.sender_email:
        # "jane.doe@shop.com" -> "Jane Doe"
        local = parsed.sender_email.split("@")[0]
        ex.name = " ".join(p.capitalize() for p in re.split(r"[._-]+", local) if p)
    if parsed.sender_email and "@" in parsed.sender_email:
        domain = parsed.sender_email.split("@")[1]
        generic = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "aol.com"}
        if domain.lower() not in generic:
            ex.company = domain.split(".")[0].capitalize()
    ex.intent = parsed.subject or (parsed.body[:120] + "…" if len(parsed.body) > 120 else parsed.body)
    return ex


def claude_extract(parsed: ParsedEmail) -> Extraction:
    """Extract with Claude via forced tool use. Raises on any failure."""
    import anthropic

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        "Extract sales-lead information from this inbound email to Estimoto "
        "(an AI estimating tool for auto-body shops).\n\n"
        f"From: {parsed.sender_name} <{parsed.sender_email}>\n"
        f"Subject: {parsed.subject}\n\n{parsed.body[:6000]}"
    )
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_lead"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    data = tool_use.input
    return Extraction(
        name=str(data.get("name", "")),
        email=str(data.get("email", "")) or parsed.sender_email,
        phone=str(data.get("phone", "")),
        company=str(data.get("company", "")),
        intent=str(data.get("intent", "")),
        estimated_value=data.get("estimated_value"),
        method="claude",
    )


def extract(parsed: ParsedEmail) -> Extraction:
    if get_settings().anthropic_api_key:
        try:
            return claude_extract(parsed)
        except Exception:
            pass
    return fallback_extract(parsed)
