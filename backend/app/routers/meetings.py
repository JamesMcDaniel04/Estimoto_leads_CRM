from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_user
from ..db import get_db
from ..ics import meeting_to_ics
from ..models import Activity, Lead, Meeting
from ..schemas import MeetingCreate, MeetingOut

router = APIRouter(
    prefix="/api/meetings", tags=["meetings"], dependencies=[Depends(require_user)]
)


@router.get("", response_model=list[MeetingOut])
async def list_meetings(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Meeting).order_by(Meeting.starts_at))).all()


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(body: MeetingCreate, db: AsyncSession = Depends(get_db)):
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    lead = await db.get(Lead, body.lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    meeting = Meeting(**body.model_dump())
    db.add(meeting)
    lead.activities.append(
        Activity(
            type="meeting_scheduled",
            body=f"Meeting scheduled: {body.title} at {body.starts_at.isoformat()}",
        )
    )
    if lead.stage in ("new", "contacted", "qualified"):
        lead.activities.append(
            Activity(
                type="stage_changed",
                body=f"Stage changed from {lead.stage} to meeting_scheduled",
            )
        )
        lead.stage = "meeting_scheduled"
    await db.commit()
    return meeting


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: int, db: AsyncSession = Depends(get_db)):
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    await db.delete(meeting)
    await db.commit()


@router.get("/{meeting_id}/ics")
async def download_ics(meeting_id: int, db: AsyncSession = Depends(get_db)):
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    lead = await db.get(Lead, meeting.lead_id)
    content = meeting_to_ics(meeting, attendee_email=lead.email if lead else "")
    return Response(
        content=content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="meeting-{meeting.id}.ics"'
        },
    )
