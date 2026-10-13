from app.worker.celery_app import celery_app


@celery_app.task(name="sal.worker.health_check")
def worker_health_check() -> str:
    return "worker_alive"


@celery_app.task(
    bind=True,
    name="sal.vehicle_verification.process",
    acks_late=True,
    max_retries=2,
)
def process_vehicle_verification_job(self, job_id: str) -> str:
    """
    Process a vehicle verification job with the FAKE provider.

    Duplicate delivery is safe: terminal or already-claimed jobs are
    not modified.
    """
    from app.database.database import SessionLocal
    from app.providers.vehicle_authority_provider import (
        get_vehicle_authority_provider,
    )
    from app.services.vehicle_verification_job_service import process_job

    db = SessionLocal()

    try:
        result = process_job(
            db, job_id, get_vehicle_authority_provider("fake")
        )
    finally:
        db.close()

    if result.action == "RETRY":
        raise self.retry(countdown=30 * 2 ** (result.attempt_count - 1))

    return result.action
