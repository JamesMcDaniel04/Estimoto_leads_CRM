import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_user
from ..config import get_settings
from ..db import get_db
from ..gmail import (
    build_auth_url,
    exchange_code,
    fetch_profile_email,
    oauth_configured,
    revoke_token,
    state as gmail_state,
    verify_oauth_state,
)
from ..models import GmailAccount

log = logging.getLogger("gmail")

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/auth-url", dependencies=[Depends(require_user)])
def auth_url():
    if not oauth_configured():
        raise HTTPException(
            status_code=400,
            detail="Google OAuth not configured — set GOOGLE_OAUTH_CLIENT_ID and "
            "GOOGLE_OAUTH_CLIENT_SECRET in backend/.env",
        )
    return {"url": build_auth_url()}


@router.get("/callback")
async def callback(
    code: str | None = None,
    oauth_state: str | None = Query(None, alias="state"),
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Google redirects the browser here. No JWT — the signed `state` nonce
    (minted by /auth-url for a logged-in user) authenticates the request."""
    front = get_settings().frontend_url
    if error or not code or not verify_oauth_state(oauth_state):
        return RedirectResponse(f"{front}/inbox?gmail=error")
    try:
        tokens = await exchange_code(code)
        refresh = tokens.get("refresh_token")
        if not refresh:
            log.error("Token exchange returned no refresh_token")
            return RedirectResponse(f"{front}/inbox?gmail=error")
        email_addr = await fetch_profile_email(tokens["access_token"])
        existing = await db.scalar(
            select(GmailAccount).where(GmailAccount.email == email_addr).limit(1)
        )
        if existing:
            existing.refresh_token = refresh
        else:
            db.add(GmailAccount(email=email_addr, refresh_token=refresh))
        await db.commit()
        return RedirectResponse(f"{front}/inbox?gmail=connected")
    except Exception:
        log.exception("Gmail OAuth callback failed")
        return RedirectResponse(f"{front}/inbox?gmail=error")


@router.get("/status", dependencies=[Depends(require_user)])
async def status(db: AsyncSession = Depends(get_db)):
    accounts = (await db.scalars(select(GmailAccount))).all()
    return {
        "configured": oauth_configured(),
        "connected": [
            {"id": a.id, "email": a.email, "connected_at": a.connected_at} for a in accounts
        ],
        "last_poll": gmail_state["last_poll"],
        "last_error": gmail_state["last_error"],
        "ingested_total": gmail_state["ingested_total"],
    }


@router.delete("/account/{account_id}", status_code=204, dependencies=[Depends(require_user)])
async def disconnect(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(GmailAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    await revoke_token(account.refresh_token)
    await db.delete(account)
    await db.commit()
