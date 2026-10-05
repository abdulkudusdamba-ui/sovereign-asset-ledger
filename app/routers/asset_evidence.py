import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.schemas.asset_evidence_review import (
    AssetEvidenceReviewHistoryResponse,
    AssetEvidenceReviewRequest,
    AssetEvidenceReviewResponse,
)
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
