# Estimoto Leads CRM

Internal CRM for Estimoto's own sales motion. Not part of the Estimoto product suite —
this tracks *our* inbound customers, not our customers' customers.

**What it does**

- **Email → lead**: paste an inbound customer email (or upload a `.eml`) and contact
  details (name, email, phone, company, intent) are extracted automatically. With an
  `ANTHROPIC_API_KEY` set, Claude does the extraction; without one, a header/regex
  fallback still works. Repeat emails from the same address attach to the existing lead.
- **Gmail auto-ingestion (native OAuth)**: set `GOOGLE_OAUTH_CLIENT_ID`/`SECRET` (the
  Estimoto Google OAuth client works — add this app's redirect URI to it and enable the
  Gmail API), then click **Connect Gmail** on the Inbox page and approve as
  hello@estimoto.io. The backend polls the Gmail API for unread inbox mail and ingests it
  through the same pipeline — no pasting, no app passwords. Messages are only marked read
  after successful ingestion, and `Message-ID` dedupe makes redelivery harmless. Status
  shows on the Email Inbox page and at `GET /api/gmail/status`; disconnect any time from
  the same page. (An app-password IMAP fallback also exists via `IMAP_ACCOUNTS`.)
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

## Deploy

The two halves deploy to different places because the backend is a long-running process
(background mail poller + SQLite file) that cannot run on serverless:

**Backend → Fly.io** (always-on machine + volume). One-time setup is documented at the
top of [backend/fly.toml](backend/fly.toml): `fly launch`, create the `crm_data` volume,
set secrets (`JWT_SECRET`, `ADMIN_*`, `GOOGLE_OAUTH_*`, `CORS_ORIGINS`, `FRONTEND_URL`),
then `fly deploy`. After deploying, add the production callback URL
(`https://<app>.fly.dev/api/gmail/callback`) to the Google OAuth client's authorized
redirect URIs alongside the localhost one.

**Frontend → Vercel** (static). The root [vercel.json](vercel.json) builds `frontend/`
from this monorepo, so importing the repo into Vercel works as-is. Set one environment
variable in the Vercel project: `VITE_API_URL=https://<app>.fly.dev` (it's baked in at
build time; leave it unset locally and the dev proxy is used). The backend's
`CORS_ORIGINS` and `FRONTEND_URL` secrets must name your Vercel domain.

## Design notes

See [docs/superpowers/specs/2026-07-31-estimoto-leads-crm-design.md](docs/superpowers/specs/2026-07-31-estimoto-leads-crm-design.md)
for architecture, data model, and the v1 scope decisions (notably: no IMAP polling or
calendar OAuth yet — the ingest endpoint is designed so an IMAP poller can be added as a
thin client later; tables are `create_all`-managed until the first breaking schema change
warrants Alembic).
