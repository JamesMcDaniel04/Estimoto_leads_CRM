import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import gmail, imap_poller
from .config import get_settings
from .db import init_db
from .models import STAGES
from .routers import auth, emails, followups, gmail as gmail_router, leads, meetings

log = logging.getLogger("main")


async def mail_poll_loop(imap_accounts: list) -> None:
    """One loop drives both ingestion sources; each cycle is fully isolated
    so a Gmail failure never stops IMAP and vice versa."""
    interval = get_settings().imap_poll_seconds
    while True:
        if imap_accounts:
            try:
                await imap_poller.poll_once(imap_accounts)
            except Exception:
                log.exception("Unexpected IMAP poller error")
        try:
            await gmail.poll_gmail_once()
        except Exception:
            log.exception("Unexpected Gmail poller error")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    poller_task = None
    try:
        imap_accounts = imap_poller.load_accounts()
    except ValueError as e:
        log.error("%s — IMAP polling disabled", e)
        imap_poller.state["last_error"] = str(e)
        imap_accounts = []
    imap_poller.state["mailboxes"] = [a.email for a in imap_accounts]
    # Gmail accounts connect at runtime via OAuth, so the loop must run
    # whenever OAuth is configured even if nothing is connected yet.
    if imap_accounts or gmail.oauth_configured():
        poller_task = asyncio.create_task(mail_poll_loop(imap_accounts))
        log.info(
            "Mail poller started (imap: %s, gmail oauth configured: %s)",
            ", ".join(imap_poller.state["mailboxes"]) or "none",
            gmail.oauth_configured(),
        )
    yield
    if poller_task:
        poller_task.cancel()
        with suppress(asyncio.CancelledError):
            await poller_task


app = FastAPI(title="Estimoto Leads CRM", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(emails.router)
app.include_router(meetings.router)
app.include_router(gmail_router.router)
app.include_router(followups.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/stages")
def stages():
    return {"stages": STAGES}
