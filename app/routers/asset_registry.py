from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.models.asset_registry import AssetRegistry

from app.schemas.asset_registry import (
    AssetRegistryCreate,
    AssetRegistryResponse
)

from app.services.asset_service import generate_sal_id


router = APIRouter(
    prefix="/registry",
    tags=["Master Registry"]
)


@router.get(
    "/",
    response_model=list[AssetRegistryResponse]
)
def get_registry(
    db: Session = Depends(get_db)
):
    return (
        db.query(AssetRegistry)
        .order_by(AssetRegistry.id.asc())
        .all()
    )


@router.post(
    "/",
    response_model=AssetRegistryResponse
)
def create_registry(
    registry: AssetRegistryCreate,
    db: Session = Depends(get_db)
):
    """
    Create a SAL master registry identity.

    The client cannot provide the SAL ID.
    SAL generates it server-side.
    """

    sal_id = generate_sal_id()

    record = AssetRegistry(
        sal_id=sal_id,
        asset_type=registry.asset_type,
        registry_id=registry.registry_id,
        owner=registry.owner,
        estimated_value=registry.estimated_value,
        status=registry.status,

        # Explicitly preserve SAL's current verification meaning.
        sal_verification="VERIFIED",

        # Government verification is separate.
        government_verification="NOT_VERIFIED",

        # Cryptographic anchoring is not yet active.
        blockchain_status="PENDING",
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
