# Attlytics

Attlytics shows you where your computer time actually goes.

A small agent runs on your machine and records which application is in front of
you. It uploads those events to a server, which groups them into **sessions** —
one continuous stretch in one application on one device. A web dashboard then
turns those sessions into totals, charts and a timeline.

Everything in the API is scoped to the logged-in user, so an account can only
ever read its own data.

## Overview

1. **The agent records.** It watches the active window and writes a row to a
   local SQLite file every time something changes, plus a heartbeat every
   minute while nothing changes.
2. **The agent uploads.** A background thread inside the agent sends unsent rows
   to the API in batches and marks them as sent. If the network is down it
   backs off and retries, so nothing is lost.
3. **The API stores and groups.** Raw events land in `heartbeats`. A separate
   worker groups them into `sessions`, which is what every read endpoint reads.
4. **The dashboard reads.** The frontend asks the API for sessions and totals
   and draws them.

The agent deliberately never decides what a "session" is. It only reports what
it saw. That keeps the grouping rules on the server, where they can change
without shipping a new agent build.

```
agent (Windows)                 api (server)                 frontend
  observe  ->  SQLite  ->  POST /api/v1/heartbeats  ->  Postgres
                                    |
                              worker groups events
                                    v
                              sessions  <----  GET /api/v1/sessions
```

## Components

### `agent/` — the desktop tracker

Python, Windows-only today. Runs in the tray with no window, and writes a log
file next to its data because a packaged app has nowhere else to put failures.

- `tracking/` decides which events to record. It emits `STATE_START` when the
  active application changes, `HEARTBEAT` while it stays the same, and
  `STATE_END` when it changes away. Idle is tracked as its own state.
- `storage/` is the local SQLite event log the uploader reads from.
- `sync_worker.py` uploads pending rows in timestamp order, with backoff.
- `identity.py` and `account.py` handle this device's identity and enrolment.
- `instance_lock.py` stops two copies of the agent running at once.
- `attlytics-agent.spec` builds the standalone executable.

### `api/` — the server

FastAPI service plus a background worker, backed by PostgreSQL. Owns users,
devices, the raw event log, derived sessions, and every read endpoint.

See [`api/README.md`](api/README.md) for how to run it and
[`api/CHECKLIST.md`](api/CHECKLIST.md) for what is left before it is
production-ready.

### `frontend/` — the dashboard

React + TypeScript single-page app. Talks only to the API; it holds no data of
its own.

### `extensions/` — planned

Empty for now. Intended for editor or browser extensions that can report
activity more precisely than window titles can.

## Stack

| Part | Uses |
|---|---|
| `agent` | Python 3.14, psutil, pywin32, pystray, Pillow, filelock, SQLite, PyInstaller |
| `api` | Python 3.14, FastAPI, Uvicorn, SQLAlchemy 2 (async) on PostgreSQL via psycopg 3, Alembic, Celery + Redis, JWT, bcrypt |
| `frontend` | React 18, TypeScript, Vite, TanStack Query, axios, Zustand, React Router |
| `extensions` | not started |

## Setup

Two ways to run this: everything in Docker, or each piece locally. Docker gets
you a working stack fastest; local is what you want while editing the agent,
which cannot run in a container because it measures the Windows machine it runs
on.

Prerequisites: Python 3.12+ (this repo runs 3.14), Node 22, and Docker Desktop
if you want the container route.

### Option A — everything in Docker

From the repo root:

```sh
docker compose up --build
```

That builds the API image, waits for Postgres to be healthy, applies migrations,
then starts the API, the sessionization worker, Celery beat, and the Vite dev
server.

| URL | What |
|---|---|
| <http://127.0.0.1:8000/api/v1/health> | API health |
| <http://127.0.0.1:8000/api/docs> | Interactive API docs |
| <http://127.0.0.1:5173> | Dashboard |

Two env files have to exist first: `api/.env` for app config and secrets, and
the root `.env` for Postgres credentials and the `db`/`redis` service names.
Details in [`api/README.md`](api/README.md).

```sh
docker compose up -d --build     # detached
docker compose logs -f api       # follow one service
docker compose down              # stop, keep the database
docker compose down -v           # stop and delete the database
```

The agent is deliberately not in the compose file. It has to run on the machine
being measured, so start it as a local process or as the built `.exe`.

### Option B — run each piece locally

**Agent** — Windows only, from the repo root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m agent.app
```

With no arguments that starts the tray app. `python -m agent.app --agent` runs
the same loop without the tray icon, which is easier to watch while developing
because the log goes to the console.

**API** — from `api/`, and it needs Postgres and Redis running:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Then the two background pieces, each in its own terminal:

```powershell
celery -A app.workers.celery_app:celery_app worker -l info
celery -A app.workers.celery_app:celery_app beat -l info
```

**Frontend** — from `frontend/`:

```powershell
npm install
npm run dev
```

### Building the agent as a Windows `.exe`

PyInstaller is not in `requirements.txt`, so install it into the same
environment first. Run the build from the **repo root** — the spec resolves
`agent/app.py` relative to it:

```powershell
pip install pyinstaller
pyinstaller --clean --noconfirm attlytics-agent.spec
```

That produces `dist\attlytics-agent.exe` — a single windowed file with no
console, so failures only show up in the log:

```powershell
.\dist\attlytics-agent.exe           # tray app
.\dist\attlytics-agent.exe --agent   # headless, with console output
```

Everything the agent writes lives in `%USERPROFILE%\.attlytics\`:

| File | What it is |
|---|---|
| `data\activity_events.db` | local SQLite queue of recorded events |
| `identity.json` | this device's id, API key and metadata |
| `agent.log` | rotating log (the only place a windowed build reports errors) |

## Key Design Decisions

### Events are append-only; sessions are derived

The agent writes facts ("at 09:14 the active app became `code.exe`"). Sessions
are a calculation on top of those facts, not something the agent reports. If the
grouping logic turns out to be wrong, it can be recomputed from the raw events
instead of waiting for every device to update.

### Grouping is a background job, not part of ingest

Ingest just writes rows and returns. A separate worker picks up unprocessed
events and builds sessions. That keeps uploads fast and lets the grouping run at
its own pace, or be re-run over history.

### Every write is safe to repeat

Uploads and session writes are both upserts — "insert, or update the row that is
already there". A device that retries an upload after a timeout, or a worker
that runs the same batch twice, produces the same result rather than duplicates.

### More than one worker can run

Unprocessed events are claimed with `SELECT ... FOR UPDATE SKIP LOCKED`, so two
workers never take the same row. Sessions are written with a single
`INSERT ... ON CONFLICT DO UPDATE` keyed on `(user_id, device_id, state_id)`,
backed by a unique constraint. Missing that constraint was a real bug: two
workers could both see "no session yet" and both insert one.

### Times are stored in UTC

Postgres columns are `timestamptz` with UTC values, and ingest **rejects** a
heartbeat whose timestamp has no UTC offset. Accepting a vague local time would
silently shift sessions by hours. Anywhere that groups by day takes an explicit
timezone, because "a day" is not the same day for everyone.

### The server decides the owner, never the request

The owner id comes from the authenticated token, not a query parameter or body
field. Device uploads are stamped with the device that authenticated them, and
the payload's own `device_id`/`user_id` are ignored. Reads return `404` rather
than `403` for another user's data, so the API does not reveal what exists.

### The agent buffers locally

The agent is the source of truth until the server confirms receipt. It keeps a
durable local queue, so a laptop that is offline for a day loses nothing and the
server never has to be reachable for tracking to keep working.


## Device registration

<!--
Space for the device registration sequence diagram.

Suggested content: agent generates installation_id -> POST /api/v1/devices/enroll
-> API returns a short-lived enrollment token -> agent opens the confirm link in
the browser -> user approves -> POST /api/v1/devices/confirm -> API links the
device to the user and returns an API key -> agent stores the key in
identity.json and starts syncing.
-->

## Pending tasks

Cross-cutting, in rough order:

- ⬜ **Finish the read API** — timeline day view, daily/hourly/heatmap,
  context-switching, focus, and especially coverage (which days had no data,
  so charts stop implying "you did nothing").
- ⬜ **Statistics rollups** — precomputed daily/hourly tables so dashboards stop
  aggregating raw sessions per request.
- ⬜ **Roles and admin privileges** — token scopes, an admin surface, and an
  audit trail for privileged reads. Today the API is single-tenant.
- ⬜ **Integration tests against a real Postgres** — the current tests stub the
  database, so nothing verifies the SQL, migrations, or concurrency behaviour.
- ⬜ **`extensions/`** — not started.

The detailed API list lives in [`api/CHECKLIST.md`](api/CHECKLIST.md).
