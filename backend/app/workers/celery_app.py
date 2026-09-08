from __future__ import annotations

from celery import Celery

from app.config import settings


celery_app = Celery(
    "fact_knowledge_layer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    imports=(
    "app.workers.tasks_ingestion",
    "app.workers.tasks_extraction",
    "app.workers.tasks_comparison",
    ),
)


@celery_app.task
def health_check() -> str:
    """Simple task used to verify Celery + Redis connectivity."""

    return "celery-ok"
