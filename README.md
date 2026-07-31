# Estimoto Leads CRM

Internal CRM for Estimoto's own sales motion. Not part of the Estimoto product suite —
this tracks *our* inbound customers, not our customers' customers.

**What it does**

- **Email → lead**: paste an inbound customer email (or upload a `.eml`) and contact
  details (name, email, phone, company, intent) are extracted automatically. With an
  `ANTHROPIC_API_KEY` set, Claude does the extraction; without one, a header/regex
  fallback still works. Repeat emails from the same address attach to the existing lead.
- **IMAP auto-ingestion**: configure `IMAP_ACCOUNTS` (e.g. hello@estimoto.io and
  estimates@estimoto.io) and the backend polls each inbox for unseen mail and ingests it
  through the same pipeline — no pasting needed. Messages are only marked read after
  successful ingestion, and `Message-ID` dedupe makes redelivery harmless. Status shows
  on the Email Inbox page and at `GET /api/emails/imap-status`.
- **Pipeline tracking**: kanban board with drag-and-drop across
  New → Contacted → Qualified → Meeting Scheduled → Proposal → Won / Lost, plus a full
  activity timeline per lead (stage changes, ingested emails, meetings, notes).
- **Meeting scheduling**: schedule meetings against a lead, view upcoming/past, and
  download an RFC 5545 `.ics` invite to add to your calendar / send to the customer.
  Scheduling a meeting auto-advances early-stage leads to *Meeting Scheduled*.

**Stack**: FastAPI + SQLAlchemy (async, SQLite by default) · Vite, React 19, TypeScript,
Tailwind CSS 4 · single-admin JWT auth.

## Run it

Backend (`http://localhost:8000`):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # set ADMIN_PASSWORD, JWT_SECRET; optionally ANTHROPIC_API_KEY
.venv/bin/uvicorn app.main:app --reload
```

Frontend (`http://localhost:5173`, proxies `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

Sign in with the `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `backend/.env`.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

Covers auth, email parsing/extraction (fallback path), lead dedupe on ingest, stage
transitions + activity logging, meeting validation, and ICS output.

## Design notes

See [docs/superpowers/specs/2026-07-31-estimoto-leads-crm-design.md](docs/superpowers/specs/2026-07-31-estimoto-leads-crm-design.md)
for architecture, data model, and the v1 scope decisions (notably: no IMAP polling or
calendar OAuth yet — the ingest endpoint is designed so an IMAP poller can be added as a
thin client later; tables are `create_all`-managed until the first breaking schema change
warrants Alembic).
