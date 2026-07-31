from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_user
from ..db import get_db
from ..models import Activity, Lead
from ..schemas import (
    ActivityOut,
    LeadCreate,
    LeadDetail,
    LeadOut,
    LeadUpdate,
    NoteCreate,
    validate_stage,
)

router = APIRouter(prefix="/api/leads", tags=["leads"], dependencies=[Depends(require_user)])


async def get_lead_or_404(lead_id: int, db: AsyncSession) -> Lead:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.get("", response_model=list[LeadOut])
async def list_leads(stage: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Lead).order_by(Lead.updated_at.desc())
    if stage is not None:
        query = query.where(Lead.stage == validate_stage(stage))
    return (await db.scalars(query)).all()


@router.post("", response_model=LeadOut, status_code=201)
async def create_lead(body: LeadCreate, db: AsyncSession = Depends(get_db)):
    validate_stage(body.stage)
    lead = Lead(**body.model_dump())
    lead.activities.append(Activity(type="created", body="Lead created manually"))
    db.add(lead)
    await db.commit()
    return lead


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    return await get_lead_or_404(lead_id, db)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: int, body: LeadUpdate, db: AsyncSession = Depends(get_db)):
    lead = await get_lead_or_404(lead_id, db)
    changes = body.model_dump(exclude_unset=True)
    if "stage" in changes and changes["stage"] != lead.stage:
        validate_stage(changes["stage"])
        lead.activities.append(
            Activity(
                type="stage_changed",
                body=f"Stage changed from {lead.stage} to {changes['stage']}",
            )
        )
    for key, value in changes.items():
        setattr(lead, key, value)
    await db.commit()
    return lead


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await get_lead_or_404(lead_id, db)
    await db.delete(lead)
    await db.commit()


@router.post("/{lead_id}/notes", response_model=ActivityOut, status_code=201)
async def add_note(lead_id: int, body: NoteCreate, db: AsyncSession = Depends(get_db)):
    lead = await get_lead_or_404(lead_id, db)
    note = Activity(type="note", body=body.body)
    lead.activities.append(note)
    await db.commit()
    return note
