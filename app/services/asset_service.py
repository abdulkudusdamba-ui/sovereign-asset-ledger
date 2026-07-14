import uuid

from sqlalchemy.orm import Session
from app.services.qr_service import generate_qr
from app.models.asset_registry import AssetRegistry
from app.enums.asset_types import AssetType


def generate_sal_id():
    return f"SAL-{uuid.uuid4().hex[:12].upper()}"


def register_asset(
    db: Session,
    asset_type: AssetType,
    registry_id: int,
    owner: str,
    estimated_value: float = 0.0,
):
    registry = AssetRegistry(
        sal_id=generate_sal_id(),
        asset_type=asset_type.value,
        registry_id=registry_id,
        owner=owner,
        estimated_value=estimated_value,
        status="Active",
    )

    db.add(registry)
    db.commit()
    db.refresh(registry)  
    # Generate QR Code 
    qr_path = generate_qr(registry.sal_id)
    return registry