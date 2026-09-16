import logging
import time

from app.db.session import SessionLocal
from app.services.session import BatchResult, sessionize_pending
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async
from app.workers.tasks import SESSIONIZE_PENDING

logger = logging.getLogger("app.workers.tasks.session")


async def _run_batch() -> BatchResult | None:
    async with SessionLocal() as db:
        return await sessionize_pending(db)


@celery_app.task(name=SESSIONIZE_PENDING)
def sessionize_pending_task() -> int | None:

    started = time.perf_counter()
    result = run_async(_run_batch())

    if result is None:
        logger.debug("No pending events")
        return None

    logger.info(
        "Batch processed events=%s created=%s updated=%s duration_ms=%s",
        result.events,
        result.created,
        result.updated,
        round((time.perf_counter() - started) * 1000),
    )

    return result.events
