from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.asset_registry import AssetRegistry
from app.models.government_verification import GovernmentVerification

router = APIRouter(
    prefix="/verify",
    tags=["Verification"]
)


@router.get("/{sal_id}")
def verify_asset(
    sal_id: str,
    db: Session = Depends(get_db)
):
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    # Find the latest government verification request
    government_verification = (
        db.query(GovernmentVerification)
        .filter(
            GovernmentVerification.asset_registry_id == asset.id
        )
        .order_by(
            GovernmentVerification.id.desc()
        )
        .first()
    )

    if government_verification:
        government_status = government_verification.status
    else:
        government_status = "NOT_VERIFIED"

    return {
        "sal_id": asset.sal_id,
        "asset_type": asset.asset_type,
        "registry_id": asset.registry_id,
        "owner": asset.owner,
        "estimated_value": asset.estimated_value,
        "status": asset.status,
        "verification": {
            "sal": "VERIFIED",
            "government": government_status,
            "blockchain": "PENDING"
        }
    }