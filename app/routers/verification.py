from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.models.asset_registry import AssetRegistry
from app.models.government_verification import GovernmentVerification
from app.models.vehicle import Vehicle


router = APIRouter(
    prefix="/verify",
    tags=["Verification"]
)


@router.get("/{sal_id}")
def verify_asset(
    sal_id: str,
    db: Session = Depends(get_db)
):
    """
    Resolve a SAL ID into the master registry identity
    and the underlying specialized asset record.

    SAL remains the persistent identity layer.
    Specialized tables remain the source of asset-specific data.
    """

    # ---------------------------------------------------------
    # 1. Find the SAL master registry identity.
    # ---------------------------------------------------------
    asset = (
        db.query(AssetRegistry)
        .filter(
            AssetRegistry.sal_id == sal_id
        )
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="SAL asset identity not found"
        )

    # ---------------------------------------------------------
    # 2. Find the latest government verification record.
    # ---------------------------------------------------------
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
        government_status = (
            asset.government_verification
            or "NOT_VERIFIED"
        )

    # ---------------------------------------------------------
    # 3. Resolve the specialized asset.
    # ---------------------------------------------------------
    asset_details = None

    if asset.asset_type.upper() == "VEHICLE":
        vehicle = (
            db.query(Vehicle)
            .filter(
                Vehicle.id == asset.registry_id
            )
            .first()
        )

        if not vehicle:
            raise HTTPException(
                status_code=409,
                detail=(
                    "SAL registry identity exists, "
                    "but the linked vehicle record was not found"
                )
            )

        asset_details = {
            "registration_number": vehicle.registration_number,
            "vin": vehicle.vin,
            "manufacturer": vehicle.manufacturer,
            "model": vehicle.model,
            "year": vehicle.year,
            "engine_number": vehicle.engine_number,
            "color": vehicle.color,
            "estimated_value": vehicle.estimated_value,
            "status": vehicle.status,
        }

    # ---------------------------------------------------------
    # 4. Return the SAL identity + specialized asset details.
    # ---------------------------------------------------------
    return {
        "sal_id": asset.sal_id,
        "asset_type": asset.asset_type,
        "registry_id": asset.registry_id,
        "owner": asset.owner,
        "estimated_value": asset.estimated_value,
        "status": asset.status,

        "asset": asset_details,

        "verification": {
            # SAL verification.
            "sal": asset.sal_verification or "VERIFIED",

            # Government verification is independent.
            "government": government_status,

            # Future cryptographic anchoring.
            "blockchain": (
                asset.blockchain_status
                or "PENDING"
            ),
        },
    }
