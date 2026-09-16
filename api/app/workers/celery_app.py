from celery import Celery

from app.core.config import get_settings
from app.workers.tasks import SESSIONIZE_PENDING

settings = get_settings()

celery_app = Celery(
    "attlytics",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks.session"],
)


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=300,
    task_time_limit=330,
    beat_schedule={
        "sessionize-pending": {
            "task": SESSIONIZE_PENDING,
            "schedule": settings.sessionize_interval_seconds,
        },
    },
)