from app.core.auth import require_role
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.asset_registry import AssetRegistry
from app.models.government_verification import GovernmentVerification
from app.schemas.government_verification import (
    GovernmentVerificationCreate,
    GovernmentVerificationResponse,
    GovernmentVerificationDecision,
)

router = APIRouter(
    prefix="/government-verification",
    tags=["Government Verification"]
)


@router.post(
    "/request",
    response_model=GovernmentVerificationResponse
)
def request_government_verification(
    request: GovernmentVerificationCreate,
    db: Session = Depends(get_db)
):
    asset = (
        db.query(AssetRegistry)
        .filter(
            AssetRegistry.id == request.asset_registry_id
        )
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="SAL asset not found"
        )

    verification = GovernmentVerification(
        asset_registry_id=asset.id,
        authority=request.authority,
        reference_number=request.reference_number,
        notes=request.notes,
        status="PENDING",
    )

    db.add(verification)

    # Keep the asset itself marked as not yet government verified.
    asset.government_verification = "PENDING"

    db.commit()
    db.refresh(verification)

    return verification


# =====================================================
# GOVERNMENT VERIFICATION DECISION
# =====================================================

@router.patch(
    "/{verification_id}/decision",
    response_model=GovernmentVerificationResponse
)
def decide_government_verification(
    verification_id: int,
    decision: GovernmentVerificationDecision,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["government"]))
):
    verification = (
        db.query(GovernmentVerification)
        .filter(
            GovernmentVerification.id == verification_id
        )
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=404,
            detail="Government verification request not found"
        )

    if verification.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail="Only PENDING verification requests can be decided"
        )

    if decision.status not in ["VERIFIED", "REJECTED"]:
        raise HTTPException(
            status_code=400,
            detail="Decision must be VERIFIED or REJECTED"
        )

    verification.status = decision.status
    verification.verified_by = decision.verified_by

    if decision.notes:
        verification.notes = decision.notes

    verification.verified_at = datetime.utcnow()

    asset = (
        db.query(AssetRegistry)
        .filter(
            AssetRegistry.id == verification.asset_registry_id
        )
        .first()
    )

    if asset:
        asset.government_verification = decision.status

    db.commit()
    db.refresh(verification)

    return verification