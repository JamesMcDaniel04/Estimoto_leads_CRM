from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_user
from ..db import get_db
from ..extraction import ParsedEmail, extract, parse_eml, parse_pasted
from ..models import Activity, EmailMessage, Lead
from ..schemas import IngestRequest, IngestResponse

router = APIRouter(prefix="/api/emails", tags=["emails"], dependencies=[Depends(require_user)])


async def _ingest(parsed: ParsedEmail, db: AsyncSession) -> IngestResponse:
    ex = extract(parsed)

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
        )
    )
    lead.activities.append(
        Activity(
            type="email_ingested",
            body=f"Email ingested: {parsed.subject or '(no subject)'}",
        )
    )
    await db.commit()
    return IngestResponse(lead=lead, lead_created=created, extraction_method=ex.method)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(body: IngestRequest, db: AsyncSession = Depends(get_db)):
    return await _ingest(parse_pasted(body.raw_text), db)


@router.post("/ingest-eml", response_model=IngestResponse)
async def ingest_eml(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await _ingest(parse_eml(await file.read()), db)
