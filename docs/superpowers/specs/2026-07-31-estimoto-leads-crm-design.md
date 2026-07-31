# Estimoto Leads CRM — Design

**Date:** 2026-07-31
**Status:** Approved for v1 build (autonomous session; decisions documented for async review)

## Purpose

An internal sales CRM for Estimoto's own sales motion. Inbound customer emails arrive at
hello@estimoto.io; today follow-up is manual. This tool:

1. Extracts structured customer info from inbound emails (AI-assisted).
2. Schedules meetings with prospects and produces calendar (.ics) invites.
3. Tracks each lead's progress through the sales pipeline.

Explicitly **not** part of the Estimoto product suite — no shared tenancy, database, or
deploy pipeline with the product. Standalone repo.

## Scope (v1)

**In:**
- Single-admin login (env-configured credentials, JWT sessions).
- Lead records: contact info, company, source, estimated deal value, stage, notes.
- Email ingestion: paste raw email text or upload `.eml`; Claude extracts contact/company/
  intent into structured fields; fallback header/regex parser works with no API key.
- Dedupe: ingested emails match existing leads by sender email address.
- Pipeline kanban: New → Contacted → Qualified → Meeting Scheduled → Proposal → Won / Lost,
  drag-and-drop stage changes.
- Meetings: create against a lead, list upcoming, download `.ics` invite.
- Activity timeline per lead: auto-logged events (created, email ingested, stage changed,
  meeting scheduled) plus manual notes.

**Out (deliberately, v1):**
- IMAP/Gmail auto-polling and calendar OAuth (needs credentials to be provisioned; the
  ingestion endpoint is designed so an IMAP poller can be added as a thin client later).
- Multi-user accounts/roles, email sending, reminders, reporting dashboards.

## Architecture

Monorepo:

```
backend/   FastAPI + SQLAlchemy 2 (async) + SQLite (aiosqlite); Postgres-ready via DATABASE_URL
frontend/  Vite + React 19 + TypeScript + Tailwind CSS 4
```

Mirrors the Estimoto product stack so maintenance context transfers, without sharing code.

### Backend components

- `app/config.py` — pydantic-settings; env: `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`,
  `ADMIN_PASSWORD`, `ANTHROPIC_API_KEY` (optional), `CORS_ORIGINS`.
- `app/models.py` — `Lead`, `EmailMessage`, `Meeting`, `Activity`.
- `app/extraction.py` — email → structured lead fields. Claude (tool-forced structured
  output) when a key is configured; deterministic header/regex fallback otherwise or on API
  failure. Never blocks ingestion.
- `app/ics.py` — RFC 5545 `.ics` generation (no external lib).
- `app/routers/` — `auth`, `leads`, `emails`, `meetings`.
- Tables auto-created on startup (`create_all`) — acceptable for a fresh internal tool;
  introduce Alembic when the first breaking schema change lands.

### Data model

- **Lead**: id, name, email (unique-ish match key), phone, company, source, stage,
  estimated_value, notes, timestamps.
- **EmailMessage**: id, lead_id (FK), subject, sender, received_at, raw_body, extraction
  JSON, extraction_method (`claude` | `fallback`).
- **Meeting**: id, lead_id (FK), title, starts_at, ends_at, location, notes.
- **Activity**: id, lead_id (FK), type (`created`, `email_ingested`, `stage_changed`,
  `meeting_scheduled`, `note`), body, created_at.

### Flow: email → lead

1. `POST /api/emails/ingest` with raw text or `.eml` upload.
2. Parse headers/body (`email` stdlib for `.eml`; heuristics for pasted text).
3. Extract structured fields (Claude or fallback).
4. Match existing lead by sender email → attach; else create lead in stage `new`.
5. Log `email_ingested` activity. Response returns the lead + extraction, flagged as
   created or matched.

### Error handling

- Claude failures degrade to the fallback extractor and record `extraction_method` so the
  operator can re-run later; ingestion never 500s on extraction problems.
- Stage changes validate against the stage enum; unknown stages 422.
- Auth: all `/api/*` except `/api/auth/login` and `/health` require a valid Bearer JWT.

### Testing

Backend pytest (httpx ASGI client, in-memory SQLite): auth flow, ingestion (fallback path +
mocked Claude path), lead dedupe, stage transitions + activity logging, ICS output.
Frontend kept simple enough to verify by build + typecheck in v1.

## Alternatives considered

- **Next.js single app** — fewer moving parts, but diverges from the team's Python/FastAPI
  muscle memory and complicates the later IMAP-poller worker.
- **Supabase-backed** — reuses existing auth, but couples the internal tool to product
  infrastructure this tool is explicitly meant to stay out of.
- **IMAP polling in v1** — highest automation payoff but requires mailbox credentials;
  deferred to keep v1 shippable without provisioning secrets.
