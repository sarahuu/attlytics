# Attlytics API

Versioned FastAPI service backed by PostgreSQL. Everything for the API lives in
this `api/` directory — it is independent of the `agent/` tracker code.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2 (ORM) on PostgreSQL (`psycopg` v3)
- Pydantic v2 + pydantic-settings (config from env / `.env`)
- Alembic (DB migrations)
- pytest (tests)

## Layout

```
api/
├── app/
│   ├── main.py          # app factory: middleware, lifespan, router mount
│   ├── core/            # settings + logging
│   ├── db/              # engine, session factory, declarative Base
│   ├── models/          # SQLAlchemy ORM models (heartbeats, ...)
│   ├── schemas/         # Pydantic request/response models
│   ├── services/        # business logic called by endpoints
│   └── api/v1/          # versioned routers and endpoints
├── alembic/             # DB migrations
├── tests/
├── CHECKLIST.md         # production-readiness checklist
├── .env.example
└── requirements.txt
```

## Quickstart

1. Create the database (Postgres must be running):

   ```sh
   createdb attlytics
   # or: psql -U postgres -c "CREATE DATABASE attlytics;"
   ```

2. Configure environment:

   ```sh
   cp .env.example .env     # then edit DATABASE_URL to match your Postgres
   ```

3. Install and run (PowerShell from this `api/` directory):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

4. Check it works:

   - Health / DB probe: <http://127.0.0.1:8000/api/v1/health>
   - Interactive docs: <http://127.0.0.1:8000/docs>
   - OpenAPI JSON: <http://127.0.0.1:8000/api/v1/openapi.json>

5. Run the tests:

   ```powershell
   pytest
   ```

## Versioning

Routes are mounted under `/api/v1` (see `app/main.py`). Keep v1 stable; add
breaking changes as a new `app/api/v2` router rather than editing v1.

## Migrations

Alembic is configured and the first migration (`0001_create_heartbeats`)
creates the `heartbeats` table, mirroring the heartbeat event the agent emits
(`agent/tracking/activity_tracker.py`).

When you add or change ORM models in `app/models/`, generate a new migration
and apply it:

```sh
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Ingesting heartbeats from devices

The plan: each local device's agent records events, a local sync worker pushes
them to this API, and the API stores them in Postgres. The data layer for that
push already exists but is not exposed over HTTP yet:

- `app/models/heartbeat.py` — the `heartbeats` table
- `app/schemas/heartbeat.py` — `HeartbeatCreate` (one pushed event) and the
  batch result model
- `app/services/heartbeats.py` — `ingest_heartbeats(...)`, an idempotent bulk
  insert (`ON CONFLICT DO NOTHING` keyed on the client event `id`)

To expose it, add a `POST /api/v1/heartbeats` route that validates a
`list[HeartbeatCreate]` and calls `ingest_heartbeats`. The local worker must
flatten each agent event's `metadata` (`process_id`, `window_title`) into the
top-level fields the schema expects.
