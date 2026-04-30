from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
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
    task_routes={
        "app.worker.tasks.process_document": {"queue": "documents"},
    },
    task_default_queue="documents",
    # Retry settings
    task_max_retries=3,
    task_default_retry_delay=5,
)
