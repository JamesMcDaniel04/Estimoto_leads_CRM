"""Shared ingestion pipeline: a parsed email becomes a new or updated lead.

Used by both the manual ingest endpoints and the IMAP poller, so behavior
(extraction, dedupe, activity logging) is identical regardless of how the
email arrived.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .extraction import ParsedEmail, extract
from .models import Activity, EmailMessage, Lead
from .schemas import IngestResponse


async def ingest_parsed(
    parsed: ParsedEmail, db: AsyncSession, mailbox: str = ""
) -> IngestResponse:
    # Exact-message dedupe: repeated polls or re-uploads of the same email
    # must not create duplicate records.
    if parsed.message_id:
        existing = await db.scalar(
            select(EmailMessage).where(EmailMessage.message_id == parsed.message_id).limit(1)
        )
        if existing is not None:
            lead = await db.get(Lead, existing.lead_id)
            return IngestResponse(lead=lead, lead_created=False, extraction_method="duplicate")

    # The Claude path uses the synchronous SDK — run it in a worker thread so
    # a slow API call never stalls the event loop (poller + all requests).
    ex = await asyncio.to_thread(extract, parsed)

    lead = None
    match_email = ex.email or parsed.sender_email
    if match_email:
        lead = await db.scalar(select(Lead).where(Lead.email == match_email).limit(1))

    created = lead is None
    if created:
        lead = Lead(
            name=ex.name,
            email=match_email,
            phone=ex.phone,
            company=ex.company,
            source="inbound_email",
            stage="new",
            estimated_value=ex.estimated_value,
            notes=ex.intent,
        )
        lead.activities.append(Activity(type="created", body="Lead created from inbound email"))
        db.add(lead)
    else:
        # Fill blanks only — never overwrite operator-entered data.
        if not lead.phone and ex.phone:
            lead.phone = ex.phone
        if not lead.company and ex.company:
            lead.company = ex.company

    lead.emails.append(
        EmailMessage(
            subject=parsed.subject,
            sender=parsed.sender_email,
            raw_body=parsed.body,
            extraction_json=ex.to_json(),
            extraction_method=ex.method,
            message_id=parsed.message_id,
            mailbox=mailbox,
        )
    )
    lead.activities.append(
        Activity(
            type="email_ingested",
            body=f"Email ingested{f' via {mailbox}' if mailbox else ''}: "
            f"{parsed.subject or '(no subject)'}",
        )
    )
    await db.commit()
    return IngestResponse(lead=lead, lead_created=created, extraction_method=ex.method)
