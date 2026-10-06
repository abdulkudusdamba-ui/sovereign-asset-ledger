from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "sovereign_asset_ledger",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
)

celery_app.autodiscover_tasks(
    packages=["app.worker"],
)
