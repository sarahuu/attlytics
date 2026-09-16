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
   - Interactive docs: <http://127.0.0.1:8000/api/docs>
   - OpenAPI JSON: <http://127.0.0.1:8000/api/v1/openapi.json>

5. Run the tests:

   ```powershell
   pytest
   ```

## Running with Docker

`api/`, the sessionization worker, and the Celery beat scheduler all run from
one image; only the command differs. Postgres and Redis come from the compose
file, so nothing needs to be installed locally.

1. Create the app env file (secrets and app settings):

   ```sh
   cp .env.example .env
   ```

   `docker-compose.yml` sets no environment variables of its own. Everything it
   injects arrives through `env_file`: `api/.env` for app config and secrets,
   and the checked-in `.env` for container-only values — Postgres
   credentials plus the `db` and `redis` hostnames, which resolve only inside
   the compose network.

2. Build and start everything:

   ```sh
   docker compose up --build
   ```

3. Check it works:

   - API: <http://127.0.0.1:8000/api/v1/health>
   - Docs: <http://127.0.0.1:8000/api/docs>
   - Frontend: <http://127.0.0.1:5173>

| Service | Role | Notes |
|---|---|---|
| `db` | PostgreSQL 16 | Published on host `5433` to avoid clashing with a local Postgres on 5432 |
| `redis` | Celery broker + result backend | Published on host `6380` for the same reason |
| `migrate` | `alembic upgrade head` | Runs once and exits; everything else waits for it |
| `api` | Uvicorn | <http://127.0.0.1:8000> |
| `worker` | Celery worker | Scale freely: `docker compose up --scale worker=4` |
| `beat` | Celery beat | **Must stay at one replica** — no distributed lock |
| `web` | Vite dev server | <http://127.0.0.1:5173>; installs npm packages on first start |

`web` reads `VITE_API_BASE_URL` from `.env`. It has to stay
browser-reachable: the compose hostname `api` only resolves inside the compose
network, and the *browser* is what calls the API. Vite inlines this value when
the dev server starts, so changing it requires a restart.

Useful commands:

```sh
docker compose logs -f worker      # follow worker logs
docker compose restart worker      # pick up code changes
docker compose down                # stop, keep the database
docker compose down -v             # stop and delete the database volume
```

The worker is safe to scale because heartbeat claiming uses
`SELECT ... FOR UPDATE SKIP LOCKED` and session writes are a single
`INSERT ... ON CONFLICT DO UPDATE` keyed on `(user_id, device_id, state_id)`.

## Versioning

Routes are mounted under `/api/v1` (see `app/main.py`). Keep v1 stable; add
breaking changes as a new `app/api/v2` router rather than editing v1.

## Migrations

Alembic is configured and the migration chain builds the full schema: identity
(`users`, `devices`, `user_api_keys`, `revoked_tokens`), ingestion
(`heartbeats`) and the derived `sessions` table. Migrations read `DATABASE_URL`
from settings rather than `alembic.ini`, so the same command works locally and
inside a container.

When you add or change ORM models in `app/models/`, generate a new migration
and apply it:

```sh
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## API surface

Everything is mounted under `/api/v1` (see `app/api/v1/router.py`).

### Implemented

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness + database readiness probe |
| `POST` | `/heartbeats` | Batch ingest of agent events, idempotent on `(device_id, local_id)` |
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Log in; refresh token set as an HttpOnly cookie |
| `POST` | `/auth/refresh` | Rotate the refresh cookie, return a new access token |
| `POST` | `/auth/logout` | Revoke the refresh cookie and access token |
| `GET` | `/users/me` | Current user |
| `POST` | `/devices/enroll` | Enroll a device, receive a signed device token (no auth) |
| `POST` | `/devices/confirm` | Link the device to the user, deliver an API key |
| `GET` | `/sessions` | Session list, filtered by window/application/device/source, keyset-paginated |
| `GET` | `/sessions/{id}` | One session, owner-scoped |
| `GET` | `/stats/summary` | Totals over a window: duration, sessions, active days, longest session, first/last activity |
| `GET` | `/stats/applications` | Time per application plus share of the whole window |

Interactive docs are at `/api/docs`, redoc at `/api/redoc`, and the schema at
`/api/v1/openapi.json`.


### Planned — reads and analytics

Not built yet. Every one must be owner-scoped, keyset-paginated, and accept an
explicit timezone, since `date_trunc` buckets in the session timezone rather
than the user's.

- **Timeline** — `GET /timeline?date=`, `GET /sessions/{id}/heartbeats`
- **Aggregates** — `GET /stats/daily`, `/stats/hourly`, `/stats/heatmap`,
 
Not built yet. Every one must be owner-scoped, keyset-paginated, and accept an
explicit timezone, since `date_trunc` buckets in the session timezone rather
than the user's.

- **Timeline** — `GET /sessions`, `GET /sessions/{id}`, `GET /timeline?date=`
- **Aggregates** — `GET /stats/summary`, `/stats/applications`, `/stats/daily`,
  `/stats/hourly`, `/stats/heatmap`, `/stats/devices`
- **Behaviour** — `GET /stats/context-switching`, `GET /stats/focus`
- **Data trust** — `GET /devices`, `GET /devices/{id}/lag`, `GET /coverage`
- **Privacy** — `GET /export`, `DELETE /sessions`

`/coverage` is worth building early: without it, charts read as "you did
nothing" on days a device was offline.

### Authorization

Every endpoint is scoped to the **authenticated user**. The owner id comes from
the access token (`get_current_user`), never from a request parameter, so the
`user_id` filter is applied in SQL rather than checked after the fact. A
`?device_id=` filter narrows *within* the caller's own data and can never widen
it. Requesting another user's session by id returns `404` rather than `403`, so
existence is not leaked.

There are no roles yet — the API is single-tenant: one user, their own devices,
their own sessions. Roles and admin-level privileges are planned; see the
roadmap below.

## Roadmap

- ✅ **Composite session indexes** — `(user_id, start_time)` and `(user_id, application, start_time)`.
- ⬜ **`heartbeats` pending index** — partial `(device_id, timestamp) WHERE processed_at IS NULL` for the sessionization scan.
- ⬜ **Statistics rollups** — `daily_stats` / `hourly_stats` per `(user_id, device_id, day, application)`, written by a beat task that recomputes a trailing window so late and clock-skewed events self-heal, upserted so reruns are idempotent.
- ⬜ **Serve reads from rollups** — keep the direct-query path for ranges outside the materialized windows.
- ⬜ **Remaining read endpoints** — timeline day view, daily/hourly/heatmap, context-switching, focus, coverage, export.
- ⬜ **Roles and admin privileges** — token scopes, admin user/device management, cross-tenant repo
Order of work: read indexes → rollups → `heartbeats` partitioning → worker
sharding. Only the last one affects correctness, and it is already correct —
the rest are performance.
