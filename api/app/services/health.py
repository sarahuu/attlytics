import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def check_database(db: Session) -> tuple[bool, str]:
    """Return (ok, detail): can we reach Postgres right now?"""
    try:
        db.execute(text("SELECT 1"))
        return True, "up"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Database health check failed")
        return False, f"down ({type(exc).__name__})"


# ---------------------------------------------------------------------------
# Additional probes (commented out until their dependencies come online).
#
# Each probe has the same (ok, detail) contract as check_database above, so
# enabling one is just two lines inside build_health_report:
#
#     ok, detail = check_redis()
#     checks["redis"] = detail
#
# def check_redis() -> tuple[bool, str]:
#     """(ok, detail) whether the shared cache answers PING."""
#     try:
#         # client = redis.from_url(get_settings().redis_url, socket_timeout=2)
#         # client.ping()
#         return True, "up"
#     except Exception as exc:  # noqa: BLE001
#         logger.exception("Redis health check failed")
#         return False, f"down ({type(exc).__name__})"
#
#
# def check_migrations() -> tuple[bool, str]:
#     """(ok, detail) whether the DB schema is at the latest Alembic revision."""
#     try:
#         # Compare `alembic current` with `alembic heads`; return False when
#         # they differ so a deploy that skipped a migration is caught here.
#         return True, "up_to_date"
#     except Exception as exc:  # noqa: BLE001
#         logger.exception("Migration health check failed")
#         return False, f"error ({type(exc).__name__})"
#
#
# def check_ingest_freshness(db: Session) -> tuple[bool, str]:
#     """(ok, detail) whether heartbeats have arrived recently."""
#     try:
#         # newest = db.scalar(select(func.max(Heartbeat.received_at)))
#         # fresh = newest is not None and (
#         #     datetime.now(timezone.utc) - newest < timedelta(minutes=5)
#         # )
#         # return fresh, "receiving" if fresh else "stale"
#         return True, "n/a"
#     except Exception as exc:  # noqa: BLE001
#         logger.exception("Ingest freshness check failed")
#         return False, f"error ({type(exc).__name__})"
# ---------------------------------------------------------------------------


def build_health_report(db: Session, version: str) -> dict[str, str]:
    """Run the enabled probes and aggregate them into a health report.

    Returns a dict whose keys map 1:1 onto schemas.health.HealthResponse.
    """
    checks: dict[str, str] = {}

    db_ok, db_detail = check_database(db)
    checks["database"] = db_detail

    # Enable additional probes here as their dependencies come online, e.g.:
    #
    #   redis_ok, redis_detail = check_redis()
    #   checks["redis"] = redis_detail
    #
    #   migrations_ok, migrations_detail = check_migrations()
    #   checks["migrations"] = migrations_detail
    #
    #   fresh_ok, fresh_detail = check_ingest_freshness(db)
    #   checks["ingest_freshness"] = fresh_detail

    overall = "ok" if all(value == "up" for value in checks.values()) else "degraded"
    return {"status": overall, "version": version, "checks": checks}
