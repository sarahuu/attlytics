# API Production Checklist

Status key: ✅ wired into the scaffold · ⬜ still to do (listed in the order you should do them)

## 0. Foundations — do first, everything builds on this
- ⬜ **refresh the migration baseline** — model has outrun `alembic/0001` (missing `local_id`/UUIDs/timestamp type); make `alembic upgrade head` work on a dev DB
- ✅ structured logs with env-driven `LOG_LEVEL` (logging seed is already here)
- ⬜ **request-id middleware** → every log line carries a correlation id (cheap now, painful to retrofit)
- ✅ `/api/v1/health` DB readiness probe (your first monitoring signal)
- ⬜ expand readiness: migration state + last-ingest freshness (see `services/health.py`)
- ⬜ stand up ephemeral-Postgres tests (testcontainers) and write tests *with* each feature

## 1. Identity & data model — user, device, sessions
- ⬜ add `users`, `devices`, `sessions` models (with migrations)
- ⬜ **add `device_id` FK to `heartbeats`** — without attribution there is no multi-device tracking
- ⬜ **make `local_id` unique per device** (`UNIQUE(device_id, local_id)`) — it's globally unique today, which breaks at device #2
- ⬜ enrollment: register device → server issues `device_id` + one-time device secret; store only a hash server-side; rotate/revoke
- ⬜ user auth (OAuth2/JWT/API keys) with scope/permission checks, not just "is logged in"

## 2. Device auth & ingestion security
- ⬜ **device auth on `POST /heartbeats`** — per-device API key or HMAC; stamp `device_id` from auth, never trust the body
- ⬜ scope every read/write to the authenticated owner (no cross-tenant data)
- ✅ Pydantic schemas validate requests; enum allow-lists via `app/choices.py`
- ⬜ reject impossible values (future timestamps, absurd durations, oversized strings)
- ⬜ central exception handler → one consistent JSON error shape + correlation id, no stack traces

## 3. On-device sync worker
- ⬜ read `PENDING` events from local SQLite; batch-POST with device auth; mark `SYNCED`/`FAILED` + retry with backoff; offline buffering

## 4. Server-side sessionization
- ⬜ decide inline-vs-worker (recommend out-of-band worker as devices grow); append-only events → derived `sessions`; idempotent/backfill-safe; handle device clock skew

## 5. Analytics endpoints
- ⬜ time-per-app/day/user/device; sessions; aggregates in SQL; owner-scoped + paginated

## 6. Abuse prevention & monitoring
- ⬜ rate limiting per device key + IP (slowapi or platform gateway) — needs Phase 2 keys, keep the per-key hook
- ⬜ batch-size and payload-size caps on `POST /heartbeats`
- ⬜ trust only a known reverse proxy (`trustedhosts` + proxy headers); disable `/docs` in prod
- ⬜ **metrics (Prometheus)** — request volume/latency, ingest lag, DB pool usage
- ⬜ **alerts** on 5xx / stale ingest / queue backlog
- ⬜ **log hygiene** — no window titles, tokens, or PII in logs/error bodies; ship logs to a sink (aggregation/search) with the request-id

## 7. Privacy & data retention
- ⬜ activity telemetry (window titles) is personal data — retention window + purge job
- ⬜ data minimization + opt-out/consent story + privacy notice

## 8. Deployment & operational resilience
- ⬜ API + sessionizer worker as separate containers; migrations as a deploy job; fail deploy if `alembic current != head`
- ✅ secrets only in `.env` (git-ignored); `DATABASE_URL` never hardcoded
- ⬜ prod secrets from a secret store, rotated; least-privilege Postgres role + private network
- ⬜ TLS end-to-end + HSTS
- ⬜ Postgres backups (`pg_dump` / WAL archiving) with a **tested restore**
- ⬜ monitoring dashboard for the metrics/alerts from Phase 6
- ⬜ written API inventory; audit which environments expose OpenAPI

## 9. Testing & CI (continuous — not a final phase)
- ✅ health endpoint smoke test (async fake-session)
- ⬜ integration tests against real Postgres: auth, ingest, idempotent path (duplicate → `skipped`)
- ⬜ sessionization + analytics tests (ordering, gaps, cross-tenant isolation)
- ⬜ dependency audit (`pip-audit`), secret scanning, lint/SAST in CI

