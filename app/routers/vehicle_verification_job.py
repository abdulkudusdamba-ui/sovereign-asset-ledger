import logging
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.models.asset_registry import AssetRegistry
from app.schemas.vehicle_verification_job import (
    VehicleVerificationJobCreate,
    VehicleVerificationJobResponse,
)
from app.services import vehicle_verification_job_service as service
from app.services.vehicle_identity_service import (
    VehicleIdentityConflictError,
    VehicleIdentityNotFoundError,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vehicle-verification-jobs",
    tags=["Vehicle Verification Jobs"],
)

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def enqueue_job(job_id: str) -> None:
    from app.worker.tasks import process_vehicle_verification_job

    process_vehicle_verification_job.delay(job_id)


def _to_response(db: Session, job) -> dict:
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == job.asset_registry_id)
        .first()
    )

    return {
        "job_id": job.job_id,
        "sal_id": asset.sal_id if asset else None,
        "status": job.status,
        "outcome": job.outcome,
        "mismatched_fields": (
            job.mismatched_fields.split(",")
            if job.mismatched_fields
            else []
        ),
        "provider": job.provider,
        "attempt_count": job.attempt_count,
        "last_error_code": job.last_error_code,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


@router.post(
    "",
    response_model=VehicleVerificationJobResponse,
    status_code=202,
)
def create_vehicle_verification_job(
    request: VehicleVerificationJobCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    if idempotency_key is not None and not IDEMPOTENCY_KEY_PATTERN.match(
        idempotency_key
    ):
        raise HTTPException(
            status_code=422,
            detail="Invalid Idempotency-Key",
        )

    try:
        job, created = service.create_job(
            db,
            sal_id=request.sal_id,
            user=current_user,
            idempotency_key=idempotency_key,
        )
    except VehicleIdentityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except service.NotAVehicleAssetError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (
        VehicleIdentityConflictError,
        service.IdempotencyConflictError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if not created:
        response.status_code = 200

    # Post-commit enqueue: if it fails the job remains PENDING. There
    # is no automatic recovery sweeper; repeating the request (same
    # asset) re-enqueues a still-PENDING job.
    if job.status == service.PENDING:
        try:
            enqueue_job(job.job_id)
        except Exception:
            logger.exception("Failed to enqueue vehicle verification job")
            service.record_enqueue_failure(db, job.job_id)

    db.refresh(job)

    return _to_response(db, job)


@router.get(
    "/{job_id}",
    response_model=VehicleVerificationJobResponse,
)
def get_vehicle_verification_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(["admin", "registrar", "government"])
    ),
):
    try:
        job = service.get_job(db, job_id)
    except service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _to_response(db, job)
