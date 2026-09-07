# API Production Checklist

Status key: ✅ wired into the scaffold · ⬜ still to do before you ship

## 1. 🔐 Authentication & Authorization
- ✅ scaffold is open by default (only `/health` and `POST /heartbeats` exist)
- ⬜ pick user auth (OAuth2/JWT/API keys) and protect `/api/v1`
- ⬜ **device auth for the push endpoint** — per-device API key or HMAC-signed payloads on `POST /heartbeats`
- ⬜ scope/permission checks per resource, not just "is logged in"

## 2. 🔒 Data Protection & Transmission
- ✅ secrets only in `.env` (git-ignored); `DATABASE_URL` never hardcoded
- ⬜ TLS end-to-end (terminate at proxy/platform) + HSTS
- ⬜ prod secrets from a secret store (Key Vault/SSM), rotated — never committed
- ⬜ least-privilege Postgres role + private network (no public DB port)
- ⬜ no sensitive data (window titles, tokens, PII) in logs or error bodies

## 3. 🚧 Traffic Management & Abuse Prevention
- ✅ CORS allow-list via `CORS_ORIGINS`
- ✅ idempotent ingest — duplicate `local_id`s skipped (`ON CONFLICT DO NOTHING`)
- ⬜ rate limiting / throttling per device key + IP (slowapi or platform gateway)
- ⬜ batch-size and payload-size caps on `POST /heartbeats`
- ⬜ trust only a known reverse proxy (`trustedhosts` + proxy headers); disable `/docs` in prod

## 4. 🧪 Input Validation & Error Handling
- ✅ Pydantic schemas validate requests; enum allow-lists via `app/choices.py`
- ⬜ reject impossible values (timestamps in the future, absurd durations, oversized strings)
- ⬜ central exception handler → one consistent JSON error shape + correlation id, no stack traces
- ⬜ DB-level constraints/checks that mirror API validation (not just app-layer)

## 5. 📝 Docs, Inventory & Monitoring
- ✅ auto docs + versioned OpenAPI; `/api/v1/health` DB readiness probe
- ✅ structured logs with env-driven `LOG_LEVEL`
- ⬜ request-id middleware + metrics (Prometheus) + alerts on 5xx / stale ingest
- ⬜ written API inventory; audit which environments expose OpenAPI

## 6. 🕵️ Privacy & Data Retention
- ⬜ activity telemetry (process names, window titles) is personal data — set a retention window + purge job
- ⬜ data minimization (store window titles long-term?) and opt-out/consent story
- ⬜ document what each device sends and how it's used (privacy notice)

## 7. 💾 Operational Resiliency & Backups
- ⬜ Postgres backups (`pg_dump` / WAL archiving) with a tested restore
- ⬜ migration run/rollback procedure; fail deploy if `alembic current != head`
- ⬜ readiness includes migration state and last-ingest freshness (see `services/health.py`)

## 8. 🧪 Testing & CI Security
- ⬜ integration tests against a real Postgres (testcontainers/ephemeral DB)
- ⬜ test the idempotent path (duplicate batch → `skipped`, no error)
- ⬜ dependency audit (`pip-audit`), secret scanning, and lint/SAST in CI

