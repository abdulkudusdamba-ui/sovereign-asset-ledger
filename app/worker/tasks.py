from app.worker.celery_app import celery_app


@celery_app.task(name="sal.worker.health_check")
def worker_health_check() -> str:
    return "worker_alive"
