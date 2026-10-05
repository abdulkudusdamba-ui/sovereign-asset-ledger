import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.database.database import get_db
from app.models.asset_evidence import AssetEvidence
from app.models.asset_passport import AssetPassport
from app.schemas.asset_evidence import (
    AssetEvidenceCreate,
    AssetEvidenceResponse,
)
from app.schemas.asset_evidence_integrity import (
    AssetEvidenceIntegrityResponse,
)
from app.schemas.asset_evidence_review import (
    AssetEvidenceReviewHistoryResponse,
    AssetEvidenceReviewRequest,
    AssetEvidenceReviewResponse,
)
from app.services.evidence_storage import get_evidence_storage
from app.services.evidence_storage_service import (
    EvidenceFingerprintMismatchError,
    EvidenceStorageError,
)
from app.services.audit_service import record_audit_event
from app.services.asset_evidence_review_service import (
    AssetEvidenceConcurrencyError,
    AssetEvidenceNotFoundError,
    AssetEvidenceReviewTransitionError,
    transition_asset_evidence,
)


router = APIRouter(
    prefix="/evidence",
    tags=["Asset Evidence"],
)


@router.post(
    "/{passport_id}",
    response_model=AssetEvidenceResponse,
    status_code=201,
)
def create_evidence(
    passport_id: int,
    payload: AssetEvidenceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.id == passport_id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found",
        )

    evidence = AssetEvidence(
        evidence_id=f"SAL-EVIDENCE-{secrets.token_hex(6).upper()}",
        passport_id=passport.id,
        evidence_type=payload.evidence_type,
        title=payload.title,
        description=payload.description,
        source=payload.source,
        reference=payload.reference,
        fingerprint_sha256=payload.fingerprint_sha256,
        status="SUBMITTED",
        submitted_by=current_user.email,
        version=1,
    )

    db.add(evidence)

    try:
        db.commit()
        db.refresh(evidence)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Evidence could not be created because of a database integrity constraint",
        ) from exc

    return evidence


@router.post(
    "/{passport_id}/upload",
    response_model=AssetEvidenceResponse,
    status_code=201,
)
async def upload_evidence(
    passport_id: int,
    evidence_type: str = Form(...),
    title: str = Form(...),
    description: str | None = Form(None),
    source: str | None = Form(None),
    reference: str | None = Form(None),
    fingerprint_sha256: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    """
    Upload an Evidence file and persist its immutable metadata.

    The server calculates the SHA-256 fingerprint from the actual
    uploaded bytes. If a fingerprint is supplied by the caller, it
    must match the calculated fingerprint.

    File storage and database persistence are coordinated with
    compensating cleanup: if database persistence fails after the
    file is stored, the newly stored file is deleted.
    """

    MAX_UPLOAD_SIZE = 10 * 1024 * 1024

    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.id == passport_id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found",
        )

    evidence_type = evidence_type.strip()
    title = title.strip()

    if not evidence_type:
        raise HTTPException(
            status_code=422,
            detail="evidence_type cannot be empty",
        )

    if not title:
        raise HTTPException(
            status_code=422,
            detail="title cannot be empty",
        )

    content = await file.read(MAX_UPLOAD_SIZE + 1)

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Evidence file exceeds the maximum allowed size of 10 MiB",
        )

    evidence_id = f"SAL-EVIDENCE-{secrets.token_hex(6).upper()}"
    storage = get_evidence_storage()

    try:
        stored = storage.store(
            evidence_id=evidence_id,
            content=content,
            expected_fingerprint_sha256=fingerprint_sha256,
        )
    except EvidenceFingerprintMismatchError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except EvidenceStorageError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    evidence = AssetEvidence(
        evidence_id=evidence_id,
        passport_id=passport.id,
        evidence_type=evidence_type,
        title=title,
        description=description,
        source=source,
        reference=reference,
        fingerprint_sha256=stored.fingerprint_sha256,
        storage_backend="local",
        storage_key=f"{evidence_id}.bin",
        original_filename=file.filename,
        content_type=file.content_type,
        size_bytes=stored.size_bytes,
        status="SUBMITTED",
        submitted_by=current_user.email,
        version=1,
    )

    db.add(evidence)

    try:
        db.commit()
        db.refresh(evidence)
    except Exception as exc:
        db.rollback()

        try:
            storage.delete(evidence_id)
        except Exception:
            pass

        raise HTTPException(
            status_code=409,
            detail="Evidence file was stored but database persistence failed",
        ) from exc

    return evidence


@router.get(
    "/{passport_id}",
    response_model=list[AssetEvidenceResponse],
)
def list_evidence(
    passport_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.id == passport_id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found",
        )

    return (
        db.query(AssetEvidence)
        .filter(AssetEvidence.passport_id == passport_id)
        .order_by(
            AssetEvidence.created_at.asc(),
            AssetEvidence.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post(
    "/item/{evidence_id}/verify-integrity",
    response_model=AssetEvidenceIntegrityResponse,
)
def verify_evidence_integrity(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    evidence = (
        db.query(AssetEvidence)
        .filter(AssetEvidence.evidence_id == evidence_id)
        .first()
    )

    if not evidence:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    if not evidence.fingerprint_sha256:
        raise HTTPException(
            status_code=409,
            detail="Evidence does not have a recorded SHA-256 fingerprint",
        )

    if evidence.storage_backend != "local":
        raise HTTPException(
            status_code=409,
            detail="Evidence storage backend is not supported for integrity verification",
        )

    storage = get_evidence_storage()

    try:
        stored_fingerprint, is_valid = storage.verify_integrity(
            evidence_id=evidence.evidence_id,
            expected_fingerprint_sha256=evidence.fingerprint_sha256,
        )
    except EvidenceStorageError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    result = (
        "INTEGRITY_VALID"
        if is_valid
        else "INTEGRITY_FAILED"
    )

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_type="USER",
        action="VERIFY_INTEGRITY",
        entity_type="ASSET_EVIDENCE",
        entity_id=evidence.evidence_id,
        passport_id=evidence.passport_id,
        source="API",
        reason="Evidence file integrity verification",
        result=result,
        metadata={
            "recorded_fingerprint_sha256": evidence.fingerprint_sha256,
            "stored_fingerprint_sha256": stored_fingerprint,
            "integrity_result": result,
        },
    )

    db.commit()

    return AssetEvidenceIntegrityResponse(
        evidence_id=evidence.evidence_id,
        recorded_fingerprint_sha256=evidence.fingerprint_sha256,
        stored_fingerprint_sha256=stored_fingerprint,
        result=result,
    )


@router.get(
    "/item/{evidence_id}/download",
)
def download_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    evidence = (
        db.query(AssetEvidence)
        .filter(AssetEvidence.evidence_id == evidence_id)
        .first()
    )

    if not evidence:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    if evidence.storage_backend != "local":
        raise HTTPException(
            status_code=409,
            detail="Evidence storage backend is not supported for download",
        )

    if not evidence.storage_key:
        raise HTTPException(
            status_code=409,
            detail="Evidence does not have a stored file",
        )

    storage = get_evidence_storage()

    expected_storage_key = f"{evidence.evidence_id}.bin"
    if evidence.storage_key != expected_storage_key:
        raise HTTPException(
            status_code=409,
            detail="Evidence storage metadata is invalid",
        )

    try:
        storage_path = storage.root / expected_storage_key
        storage_path = storage_path.resolve()

        if storage_path.parent != storage.root:
            raise HTTPException(
                status_code=409,
                detail="Evidence storage metadata is invalid",
            )

        if not storage_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Evidence file not found",
            )

    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(
            status_code=409,
            detail="Evidence file could not be accessed",
        ) from exc

    return FileResponse(
        path=str(storage_path),
        media_type=evidence.content_type or "application/octet-stream",
        filename=evidence.original_filename or expected_storage_key,
    )


@router.get(
    "/item/{evidence_id}",
    response_model=AssetEvidenceResponse,
)
def get_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    evidence = (
        db.query(AssetEvidence)
        .filter(AssetEvidence.evidence_id == evidence_id)
        .first()
    )

    if not evidence:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    return evidence


@router.patch(
    "/item/{evidence_id}/review",
    response_model=AssetEvidenceReviewResponse,
)
def review_evidence(
    evidence_id: str,
    payload: AssetEvidenceReviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    try:
        evidence = transition_asset_evidence(
            db=db,
            evidence_id=evidence_id,
            new_status=payload.status,
            expected_version=payload.expected_version,
            reason=payload.reason,
            reference=payload.reference,
            reviewed_by=current_user.email,
            actor_id=current_user.id,
            actor_type="USER",
            source="API",
        )

        db.commit()
        db.refresh(evidence)

    except AssetEvidenceNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except AssetEvidenceReviewTransitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except AssetEvidenceConcurrencyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Evidence was modified by another transaction; "
                "retry with the current Evidence state"
            ),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        error_text = str(exc.orig).lower()

        if (
            "asset_evidence_review_history.reference" in error_text
            or "uq_asset_evidence_review_history_reference" in error_text
        ):
            raise HTTPException(
                status_code=409,
                detail="Evidence review reference already exists",
            ) from exc

        raise HTTPException(
            status_code=409,
            detail=(
                "Evidence review operation violates a "
                "database integrity constraint"
            ),
        ) from exc

    return evidence


@router.get(
    "/item/{evidence_id}/review-history",
    response_model=list[AssetEvidenceReviewHistoryResponse],
)
def list_evidence_review_history(
    evidence_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    evidence = (
        db.query(AssetEvidence)
        .filter(AssetEvidence.evidence_id == evidence_id)
        .first()
    )

    if not evidence:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    from app.models.asset_evidence_review_history import (
        AssetEvidenceReviewHistory,
    )

    return (
        db.query(AssetEvidenceReviewHistory)
        .filter(
            AssetEvidenceReviewHistory.evidence_id == evidence.id
        )
        .order_by(
            AssetEvidenceReviewHistory.created_at.asc(),
            AssetEvidenceReviewHistory.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
