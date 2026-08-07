import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from ..ai import ai_enabled, suggest_next_action
from ..auth import require_user
from ..db import get_db
from ..followups import compute_followups
from ..gmail import oauth_configured, state as gmail_state
from ..imap_poller import state as imap_state
from ..models import GmailAccount, Lead
from ..schemas import FollowUpOut

router = APIRouter(prefix="/api", tags=["followups"], dependencies=[Depends(require_user)])


@router.get("/followups", response_model=list[FollowUpOut])
async def list_followups(db: AsyncSession = Depends(get_db)):
    # The rules only read activities and meetings; emails (with their raw
    # bodies) would be eager-loaded for every lead without the noload.
    leads = (await db.scalars(select(Lead).options(noload(Lead.emails)))).all()
    return [
        FollowUpOut(lead=f.lead, reason=f.reason, priority=f.priority, days_idle=f.days_idle)
        for f in compute_followups(list(leads))
    ]


@router.post("/leads/{lead_id}/suggest-next")
async def suggest_next(lead_id: int, db: AsyncSession = Depends(get_db)):
    if not ai_enabled():
        raise HTTPException(
            status_code=400,
            detail="AI is not configured — set ANTHROPIC_API_KEY in backend/.env and restart",
        )
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    try:
        # Synchronous SDK call — keep it off the event loop.
        return {"suggestion": await asyncio.to_thread(suggest_next_action, lead)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI request failed: {e}")


@router.get("/integrations")
async def integrations(db: AsyncSession = Depends(get_db)):
    """One place for the UI to see what's on, off, or unconfigured."""
    gmail_accounts = (await db.scalars(select(GmailAccount))).all()
    return {
        "ai_extraction": ai_enabled(),
        "gmail": {
            "configured": oauth_configured(),
            "connected": [{"id": a.id, "email": a.email} for a in gmail_accounts],
            "last_poll": gmail_state["last_poll"],
            "last_error": gmail_state["last_error"],
            "ingested_total": gmail_state["ingested_total"],
        },
        "imap": {
            "mailboxes": imap_state["mailboxes"],
            "last_error": imap_state["last_error"],
        },
    }
