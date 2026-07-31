import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .imap_poller import load_accounts, poll_forever, state as imap_state
from .models import STAGES
from .routers import auth, emails, leads, meetings

log = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    poller_task = None
    try:
        accounts = load_accounts()
    except ValueError as e:
        log.error("%s — IMAP polling disabled", e)
        imap_state["last_error"] = str(e)
        accounts = []
    imap_state["mailboxes"] = [a.email for a in accounts]
    if accounts:
        poller_task = asyncio.create_task(poll_forever())
        log.info("IMAP poller started for: %s", ", ".join(imap_state["mailboxes"]))
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/stages")
def stages():
    return {"stages": STAGES}
