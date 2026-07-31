"""Background IMAP poller: pulls unseen messages from configured mailboxes
(e.g. hello@estimoto.io, estimates@estimoto.io) and runs them through the
same ingestion pipeline as manual uploads.

Reliability rules:
- Messages are fetched with BODY.PEEK[] so they stay unseen until ingestion
  succeeds; a crash mid-poll means the message is retried next cycle.
- Message-ID dedupe in the ingest pipeline makes retries harmless.
- Failures are per-message and per-account — one bad mailbox or message
  never blocks the others, and the poller never crashes the app.
"""

import asyncio
import imaplib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import get_settings
from .db import SessionLocal
from .extraction import parse_eml
from .ingest import ingest_parsed

log = logging.getLogger("imap_poller")


@dataclass
class ImapAccount:
    email: str
    password: str
    host: str
    port: int = 993


# Exposed via GET /api/emails/imap-status (never includes credentials).
state: dict = {
    "mailboxes": [],
    "last_poll": None,
    "last_error": None,
    "ingested_total": 0,
}


def load_accounts() -> list[ImapAccount]:
    """Parse IMAP_ACCOUNTS (a JSON list) into account objects.

    Each entry needs "email" and "password"; "host"/"port" default to
    IMAP_HOST/IMAP_PORT. Raises ValueError on malformed config so startup
    can surface it instead of silently polling nothing.
    """
    settings = get_settings()
    if not settings.imap_accounts.strip():
        return []
    try:
        entries = json.loads(settings.imap_accounts)
        return [
            ImapAccount(
                email=entry["email"],
                password=entry["password"],
                host=entry.get("host", settings.imap_host),
                port=int(entry.get("port", settings.imap_port)),
            )
            for entry in entries
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid IMAP_ACCOUNTS config: {e}") from e


def fetch_unseen(account: ImapAccount) -> list[tuple[bytes, bytes]]:
    """Return [(uid, raw_rfc822), ...] for unseen INBOX messages.

    Uses UID commands (stable across sessions) and BODY.PEEK[] so nothing
    is marked seen by the fetch itself.
    """
    conn = imaplib.IMAP4_SSL(account.host, account.port)
    try:
        conn.login(account.email, account.password)
        conn.select("INBOX")
        _, data = conn.uid("search", None, "UNSEEN")
        messages: list[tuple[bytes, bytes]] = []
        for uid in data[0].split():
            _, msg_data = conn.uid("fetch", uid, "(BODY.PEEK[])")
            for part in msg_data:
                if isinstance(part, tuple):
                    messages.append((uid, part[1]))
        return messages
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def mark_seen(account: ImapAccount, uids: list[bytes]) -> None:
    if not uids:
        return
    conn = imaplib.IMAP4_SSL(account.host, account.port)
    try:
        conn.login(account.email, account.password)
        conn.select("INBOX")
        for uid in uids:
            conn.uid("store", uid, "+FLAGS", "\\Seen")
    finally:
        try:
            conn.logout()
        except Exception:
            pass


async def poll_once(accounts: list[ImapAccount] | None = None) -> None:
    accounts = load_accounts() if accounts is None else accounts
    state["mailboxes"] = [a.email for a in accounts]
    errors: list[str] = []
    for account in accounts:
        try:
            messages = await asyncio.to_thread(fetch_unseen, account)
            ingested_uids: list[bytes] = []
            for uid, raw in messages:
                try:
                    parsed = parse_eml(raw)
                    async with SessionLocal() as db:
                        result = await ingest_parsed(parsed, db, mailbox=account.email)
                    if result.extraction_method != "duplicate":
                        state["ingested_total"] += 1
                    ingested_uids.append(uid)
                except Exception:
                    log.exception("Failed to ingest message uid=%s from %s", uid, account.email)
                    errors.append(f"{account.email}: message uid={uid.decode()} failed to ingest")
            await asyncio.to_thread(mark_seen, account, ingested_uids)
        except Exception as e:
            log.exception("IMAP poll failed for %s", account.email)
            errors.append(f"{account.email}: {e}")
    state["last_error"] = "; ".join(errors) if errors else None
    state["last_poll"] = datetime.now(timezone.utc).isoformat()


async def poll_forever() -> None:
    interval = get_settings().imap_poll_seconds
    while True:
        try:
            await poll_once()
        except Exception:
            # poll_once catches per-account errors; this is a last-resort
            # guard so the loop itself can never die.
            log.exception("Unexpected poller error")
        await asyncio.sleep(interval)
