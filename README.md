# Training Coach App

Workflow coaching layer on top of Intervals.icu:

> plan -> execution -> athlete response -> interpretation -> decision -> next plan

This repository contains the M0/M1 foundation and the first vertical slice:

**Intervals.icu -> source activities -> duplicate detection -> canonical session**

## Stack

- API: FastAPI + SQLAlchemy + PostgreSQL + Alembic
- Web: Next.js/TypeScript PWA shell
- Integration: Intervals.icu REST API (personal API key for private MVP; OAuth later)

## Quick start

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```
2. Put your Intervals personal API key in `.env`. Do **not** commit it.
3. Start PostgreSQL and API:
   ```bash
   docker compose up --build db api
   ```
4. Run migration:
   ```bash
   docker compose exec api alembic upgrade head
   ```
5. Open API docs: `http://localhost:8000/docs`

## M0/M1 vertical slice

Create an athlete:

```bash
curl -X POST http://localhost:8000/v1/dev/athletes \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Local athlete","timezone":"Europe/Warsaw"}'
```

Then sync the last 7 days using the returned athlete UUID:

```bash
curl -X POST 'http://localhost:8000/v1/sync/intervals?athlete_id=<UUID>&days=7'
```

The API will:

1. fetch activity summaries from Intervals.icu,
2. upsert raw source records,
3. detect likely duplicate recordings,
4. construct canonical sessions,
5. preserve metric-level provenance.

## Security status

The `/v1/dev/athletes` endpoint is intentionally temporary and must be removed/replaced by real authentication before public deployment. Intervals credentials remain server-side only.

## Project docs

- `docs/M0-M1.md` — implementation scope and acceptance criteria
- `docs/adr/0001-canonical-session.md` — canonical session decision
- `docs/adr/0002-webhook-plus-reconciliation.md` — sync reliability decision
