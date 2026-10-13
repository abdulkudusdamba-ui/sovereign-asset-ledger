"""
Vehicle verification job lifecycle.

States: PENDING -> IN_PROGRESS -> COMPLETED | FAILED, with
IN_PROGRESS -> PENDING for retryable provider failures. COMPLETED and
FAILED are terminal.

Transaction rules:
- Every transition is a conditional UPDATE (compare-and-set) committed
  together with its audit event.
- The claim is committed BEFORE the provider is called, so no write
  transaction is held open during the provider call.
- Completion/failure only applies if this worker still owns the claim
  (same attempt_count while IN_PROGRESS); otherwise it is a no-op.

Limitation: the compare-and-set design is intended to be safe under
concurrent PostgreSQL workers, but only sequential behaviour is tested
(SQLite). Concurrent PostgreSQL behaviour is untested.

A job's outcome is NOT government verification and never touches
AssetRegistry.government_verification or GovernmentVerification.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset_registry import AssetRegistry
from app.models.vehicle import Vehicle
from app.models.vehicle_verification_job import VehicleVerificationJob
from app.providers.vehicle_authority_provider import (
    ProviderPermanentError,
    ProviderUnavailableError,
    VehicleAuthorityProvider,
)
from app.services.audit_service import record_audit_event
from app.services.vehicle_identity_service import (
    VehicleIdentityConflictError,
    VehicleIdentityNotFoundError,
)


MAX_ATTEMPTS = 3
LEASE_SECONDS = 300
PROVIDER_NAME = "FAKE"

PENDING = "PENDING"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

ENTITY_TYPE = "VehicleVerificationJob"


class VehicleVerificationJobError(Exception):
    pass


class JobNotFoundError(VehicleVerificationJobError):
    pass


class NotAVehicleAssetError(VehicleVerificationJobError):
    pass


class IdempotencyConflictError(VehicleVerificationJobError):
    pass


@dataclass(frozen=True)
class ProcessResult:
    # NOOP, COMPLETED, FAILED, RETRY
    action: str
    attempt_count: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(value) -> str:
    return (value or "").strip().upper()


def _audit(
    db,
    job,
    *,
    action,
    result,
    actor_id=None,
    actor_type="system",
    source="worker",
    metadata=None,
):
    record_audit_event(
        db,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        entity_type=ENTITY_TYPE,
        entity_id=job.job_id,
        asset_registry_id=job.asset_registry_id,
        source=source,
        result=result,
        reference=job.job_id,
        metadata={
            "provider": job.provider,
            "attempt_count": job.attempt_count,
            **(metadata or {}),
        },
    )


def get_job(db: Session, job_id: str) -> VehicleVerificationJob:
    job = (
        db.query(VehicleVerificationJob)
        .filter(VehicleVerificationJob.job_id == job_id)
        .first()
    )

    if not job:
        raise JobNotFoundError("Vehicle verification job not found")

    return job


def _find_active(db, asset_registry_id):
    return (
        db.query(VehicleVerificationJob)
        .filter(
            VehicleVerificationJob.asset_registry_id == asset_registry_id,
            VehicleVerificationJob.provider == PROVIDER_NAME,
            VehicleVerificationJob.status.in_([PENDING, IN_PROGRESS]),
        )
        .first()
    )


def _find_by_key(db, user_id, key):
    return (
        db.query(VehicleVerificationJob)
        .filter(
            VehicleVerificationJob.requested_by == user_id,
            VehicleVerificationJob.idempotency_key == key,
        )
        .first()
    )


def create_job(
    db: Session,
    *,
    sal_id: str,
    user,
    idempotency_key: str | None = None,
) -> tuple[VehicleVerificationJob, bool]:
    """
    Create a PENDING job, or return an existing one.

    Returns (job, created). The caller is responsible for enqueueing
    after this returns; the job is already committed and stays PENDING
    if enqueueing fails.
    """

    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise VehicleIdentityNotFoundError(
            f"SAL asset '{sal_id}' was not found"
        )

    if (asset.asset_type or "").strip().lower() != "vehicle":
        raise NotAVehicleAssetError(
            "Only Vehicle assets can be verified with this job"
        )

    vehicle = (
        db.query(Vehicle).filter(Vehicle.id == asset.registry_id).first()
    )

    if not vehicle:
        raise VehicleIdentityConflictError(
            "SAL registry identity exists, but the linked vehicle "
            "record was not found"
        )

    if idempotency_key:
        existing = _find_by_key(db, user.id, idempotency_key)

        if existing:
            if existing.asset_registry_id != asset.id:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different asset"
                )
            return existing, False

    active = _find_active(db, asset.id)

    if active:
        return active, False

    job = VehicleVerificationJob(
        job_id=f"SAL-VVJ-{uuid.uuid4().hex.upper()}",
        asset_registry_id=asset.id,
        provider=PROVIDER_NAME,
        status=PENDING,
        attempt_count=0,
        requested_by=user.id,
        idempotency_key=idempotency_key,
    )

    try:
        db.add(job)
        db.flush()
        _audit(
            db,
            job,
            action="VEHICLE_VERIFICATION_JOB_CREATED",
            result="SUCCESS",
            actor_id=user.id,
            actor_type="user",
            source="api",
        )
        db.commit()
    except IntegrityError:
        # Lost a race against the one-active-job or idempotency
        # constraint; return the winner.
        db.rollback()

        existing = (
            _find_by_key(db, user.id, idempotency_key)
            if idempotency_key
            else None
        )

        if existing:
            if existing.asset_registry_id != asset.id:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different asset"
                )
            return existing, False

        active = _find_active(db, asset.id)

        if active:
            return active, False

        raise

    db.refresh(job)

    return job, True


def record_enqueue_failure(db: Session, job_id: str) -> None:
    """Audit a failed enqueue. The job stays PENDING."""
    job = get_job(db, job_id)
    _audit(
        db,
        job,
        action="VEHICLE_VERIFICATION_JOB_ENQUEUE_FAILED",
        result="FAILURE",
        source="api",
        metadata={"error_code": "ENQUEUE_FAILED"},
    )
    db.commit()


def _claim(db: Session, job_id: str, now: datetime):
    """
    Atomically move a PENDING (or lease-expired IN_PROGRESS) job to
    IN_PROGRESS. Returns (attempt_count, recovered) or None.
    """
    before = get_job(db, job_id)
    was_stale = (
        before.status == IN_PROGRESS
        and before.lease_expires_at is not None
    )

    claimable = or_(
        VehicleVerificationJob.status == PENDING,
        and_(
            VehicleVerificationJob.status == IN_PROGRESS,
            VehicleVerificationJob.lease_expires_at < now,
        ),
    )

    result = db.execute(
        update(VehicleVerificationJob)
        .where(
            VehicleVerificationJob.job_id == job_id,
            claimable,
            VehicleVerificationJob.attempt_count < MAX_ATTEMPTS,
        )
        .values(
            status=IN_PROGRESS,
            attempt_count=VehicleVerificationJob.attempt_count + 1,
            started_at=now,
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        db.rollback()
        return None

    db.expire_all()
    job = get_job(db, job_id)

    if was_stale:
        _audit(
            db,
            job,
            action="VEHICLE_VERIFICATION_JOB_LEASE_RECOVERED",
            result="SUCCESS",
        )

    _audit(
        db,
        job,
        action="VEHICLE_VERIFICATION_JOB_STARTED",
        result="SUCCESS",
    )
    db.commit()

    return job.attempt_count, was_stale


def _fail_exhausted_stale(db: Session, job_id: str, now: datetime) -> bool:
    """Fail a lease-expired job that has no attempts left."""
    result = db.execute(
        update(VehicleVerificationJob)
        .where(
            VehicleVerificationJob.job_id == job_id,
            VehicleVerificationJob.status == IN_PROGRESS,
            VehicleVerificationJob.lease_expires_at < now,
            VehicleVerificationJob.attempt_count >= MAX_ATTEMPTS,
        )
        .values(
            status=FAILED,
            last_error_code="LEASE_EXPIRED_MAX_ATTEMPTS",
            lease_expires_at=None,
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        db.rollback()
        return False

    db.expire_all()
    _audit(
        db,
        get_job(db, job_id),
        action="VEHICLE_VERIFICATION_JOB_FAILED",
        result="FAILURE",
        metadata={"error_code": "LEASE_EXPIRED_MAX_ATTEMPTS"},
    )
    db.commit()

    return True


def _finish(db, job_id, attempt, now, *, values, action, audit_result, metadata):
    """Apply a terminal/retry transition only if the claim is still ours."""
    result = db.execute(
        update(VehicleVerificationJob)
        .where(
            VehicleVerificationJob.job_id == job_id,
            VehicleVerificationJob.status == IN_PROGRESS,
            VehicleVerificationJob.attempt_count == attempt,
        )
        .values(lease_expires_at=None, updated_at=now, **values)
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        db.rollback()
        return False

    db.expire_all()
    _audit(
        db,
        get_job(db, job_id),
        action=action,
        result=audit_result,
        metadata=metadata,
    )
    db.commit()

    return True


def process_job(
    db: Session,
    job_id: str,
    provider: VehicleAuthorityProvider,
) -> ProcessResult:
    """
    Process one job. Safe to call repeatedly or concurrently for the
    same job: terminal jobs are never modified.
    """
    now = _now()

    claimed = _claim(db, job_id, now)

    if claimed is None:
        _fail_exhausted_stale(db, job_id, now)
        return ProcessResult("NOOP")

    attempt, _ = claimed

    job = get_job(db, job_id)
    vehicle = (
        db.query(Vehicle)
        .join(
            AssetRegistry,
            AssetRegistry.registry_id == Vehicle.id,
        )
        .filter(AssetRegistry.id == job.asset_registry_id)
        .first()
    )

    if vehicle is None:
        _finish(
            db, job_id, attempt, _now(),
            values={
                "status": FAILED,
                "last_error_code": "VEHICLE_NOT_FOUND",
                "completed_at": _now(),
            },
            action="VEHICLE_VERIFICATION_JOB_FAILED",
            audit_result="FAILURE",
            metadata={"error_code": "VEHICLE_NOT_FOUND"},
        )
        return ProcessResult("FAILED", attempt)

    identity = {
        "vin": vehicle.vin,
        "registration_number": vehicle.registration_number,
        "chassis_number": vehicle.chassis_number,
        "engine_number": vehicle.engine_number,
    }

    # Release the read transaction before calling the provider.
    db.rollback()

    try:
        record = provider.lookup(**identity)
    except ProviderUnavailableError:
        if attempt < MAX_ATTEMPTS:
            applied = _finish(
                db, job_id, attempt, _now(),
                values={
                    "status": PENDING,
                    "last_error_code": "PROVIDER_UNAVAILABLE",
                },
                action="VEHICLE_VERIFICATION_JOB_RETRY_SCHEDULED",
                audit_result="SUCCESS",
                metadata={"error_code": "PROVIDER_UNAVAILABLE"},
            )
            return ProcessResult("RETRY" if applied else "NOOP", attempt)

        _finish_failed(db, job_id, attempt, "PROVIDER_UNAVAILABLE")
        return ProcessResult("FAILED", attempt)
    except ProviderPermanentError:
        _finish_failed(db, job_id, attempt, "PROVIDER_ERROR")
        return ProcessResult("FAILED", attempt)
    except Exception:
        _finish_failed(db, job_id, attempt, "PROVIDER_UNEXPECTED_ERROR")
        return ProcessResult("FAILED", attempt)

    if record is None:
        mismatched = ["RECORD_NOT_FOUND"]
    else:
        mismatched = [
            name.upper()
            for name in identity
            if _norm(identity[name]) != _norm(getattr(record, name, None))
        ]

    outcome = "MISMATCH" if mismatched else "MATCH"

    applied = _finish(
        db, job_id, attempt, _now(),
        values={
            "status": COMPLETED,
            "outcome": outcome,
            "mismatched_fields": ",".join(mismatched) or None,
            "last_error_code": None,
            "completed_at": _now(),
        },
        action="VEHICLE_VERIFICATION_JOB_COMPLETED",
        audit_result="SUCCESS",
        metadata={"outcome": outcome, "mismatched_fields": mismatched},
    )

    return ProcessResult("COMPLETED" if applied else "NOOP", attempt)


def _finish_failed(db, job_id, attempt, code):
    return _finish(
        db, job_id, attempt, _now(),
        values={
            "status": FAILED,
            "last_error_code": code,
            "completed_at": _now(),
        },
        action="VEHICLE_VERIFICATION_JOB_FAILED",
        audit_result="FAILURE",
        metadata={"error_code": code},
    )
