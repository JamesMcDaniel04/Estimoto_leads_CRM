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

## Database: migrations & backups

Schema is managed by Alembic ([backend/migrations/](backend/migrations/)). On startup the
app runs `alembic upgrade head` automatically (a pre-Alembic database created by the old
`create_all` startup is detected and stamped with the baseline revision first), so
deploys apply pending migrations with no manual step. Tests use in-memory SQLite and
keep `create_all`.

To change the schema: edit [backend/app/models.py](backend/app/models.py), then

```bash
cd backend && .venv/bin/alembic revision --autogenerate -m "describe change"
```

and review the generated file in `migrations/versions/` before committing.

**Backup (production SQLite on the Fly volume):**

```bash
fly ssh console
# inside the machine — snapshot safely while the app is running:
python3 -c "import sqlite3; sqlite3.connect('/data/crm.db').execute(\"VACUUM INTO '/data/backup.db'\")"
exit
fly sftp get /data/backup.db ./crm-backup-$(date +%F).db
fly ssh console -C "rm /data/backup.db"
```

**Restore:** upload the backup and swap it in, then restart:

```bash
fly sftp shell   # put ./crm-backup-<date>.db /data/crm.db
fly apps restart estimoto-leads-crm
```

Fly also takes daily block-level volume snapshots (`fly volumes snapshots list`), which
work as a coarse fallback. There is no automated offsite backup yet — run the manual
backup before risky changes.

## Deploy

One Fly.io app serves everything: the [Dockerfile](Dockerfile) builds the frontend and
copies it into the backend image, which uvicorn serves alongside the API. A single
always-on machine is required — the background mail poller and the SQLite file on the
`crm_data` volume don't allow serverless or horizontal scaling.

One-time setup with the root [fly.toml](fly.toml):

```bash
fly launch --no-deploy          # creates the app from fly.toml
fly volumes create crm_data --region iad --size 1
fly secrets set JWT_SECRET=... ADMIN_EMAIL=... ADMIN_PASSWORD=... \
  ANTHROPIC_API_KEY=... GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
  GOOGLE_OAUTH_REDIRECT_URL=https://<app>.fly.dev/api/gmail/callback \
  FRONTEND_URL=https://<app>.fly.dev
fly deploy
```

`APP_ENV=production` is set in fly.toml, so the app refuses to boot if `JWT_SECRET` or
`ADMIN_PASSWORD` are missing or placeholders. After deploying, add the production
callback URL (`https://<app>.fly.dev/api/gmail/callback`) to the Google OAuth client's
authorized redirect URIs alongside the localhost one. Subsequent deploys are just
`fly deploy` — startup applies any pending database migrations automatically.

## Design notes

See [docs/superpowers/specs/2026-07-31-estimoto-leads-crm-design.md](docs/superpowers/specs/2026-07-31-estimoto-leads-crm-design.md)
for architecture, data model, and the v1 scope decisions (notably: no IMAP polling or
calendar OAuth yet — the ingest endpoint is designed so an IMAP poller can be added as a
thin client later). Tables are now Alembic-managed — see "Database: migrations &
backups" above.
