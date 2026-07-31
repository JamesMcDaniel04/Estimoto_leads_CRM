"""Native Gmail integration: OAuth connect flow + unread-mail polling.

Preferred over the IMAP poller — no app passwords. The operator clicks
"Connect Gmail" in the UI, approves as the mailbox account (e.g.
hello@estimoto.io), and we store the refresh token. Each poll cycle mints
an access token, lists unread INBOX messages, ingests them through the
shared pipeline, and removes the UNREAD label only after success — same
at-least-once + Message-ID-dedupe semantics as the IMAP path.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .extraction import parse_eml
from .ingest import ingest_parsed
from .models import GmailAccount

log = logging.getLogger("gmail")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
# gmail.modify = read + change labels (mark as read); no send, no delete.
SCOPE = "https://www.googleapis.com/auth/gmail.modify"

# Exposed via GET /api/gmail/status (never includes tokens).
state: dict = {
    "connected": [],
    "last_poll": None,
    "last_error": None,
    "ingested_total": 0,
}


def oauth_configured() -> bool:
    settings = get_settings()
    return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)


# --- OAuth state: a short-lived signed nonce carried through Google's
# redirect, so the unauthenticated callback can't be forged. ---------------


def make_oauth_state() -> str:
    return jwt.encode(
        {"purpose": "gmail_oauth", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )


def verify_oauth_state(value: str | None) -> bool:
    if not value:
        return False
    try:
        payload = jwt.decode(value, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return False
    return payload.get("purpose") == "gmail_oauth"


def build_auth_url() -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_url,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        # Force the consent screen so Google always returns a refresh token,
        # even when the account previously approved this client.
        "prompt": "consent",
        "state": make_oauth_state(),
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_url,
                "grant_type": "authorization_code",
                "code": code,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def revoke_token(refresh_token: str) -> None:
    """Best-effort revocation on disconnect."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(REVOKE_URL, data={"token": refresh_token})
    except httpx.HTTPError:
        log.warning("Token revocation failed (ignored)")


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def fetch_profile_email(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{GMAIL_API}/users/me/profile", headers=_auth_headers(access_token))
        resp.raise_for_status()
        return resp.json()["emailAddress"]


async def list_unread_ids(access_token: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{GMAIL_API}/users/me/messages",
            params={"q": "in:inbox is:unread", "maxResults": 25},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("messages", [])]


async def fetch_raw_message(access_token: str, message_id: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GMAIL_API}/users/me/messages/{message_id}",
            params={"format": "raw"},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        raw = resp.json()["raw"]
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


async def mark_read(access_token: str, message_id: str) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{GMAIL_API}/users/me/messages/{message_id}/modify",
            json={"removeLabelIds": ["UNREAD"]},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()


async def poll_gmail_once() -> None:
    async with SessionLocal() as db:
        accounts = (await db.scalars(select(GmailAccount))).all()
    state["connected"] = [a.email for a in accounts]
    errors: list[str] = []
    for account in accounts:
        try:
            token = await refresh_access_token(account.refresh_token)
            for message_id in await list_unread_ids(token):
                try:
                    parsed = parse_eml(await fetch_raw_message(token, message_id))
                    async with SessionLocal() as db:
                        result = await ingest_parsed(parsed, db, mailbox=account.email)
                    if result.extraction_method != "duplicate":
                        state["ingested_total"] += 1
                    # Only after successful ingestion — an unread message is
                    # our retry queue, and Message-ID dedupe makes retries safe.
                    await mark_read(token, message_id)
                except Exception:
                    log.exception("Failed to ingest Gmail message %s (%s)", message_id, account.email)
                    errors.append(f"{account.email}: message {message_id} failed to ingest")
        except Exception as e:
            log.exception("Gmail poll failed for %s", account.email)
            errors.append(f"{account.email}: {e}")
    state["last_error"] = "; ".join(errors) if errors else None
    state["last_poll"] = datetime.now(timezone.utc).isoformat()
