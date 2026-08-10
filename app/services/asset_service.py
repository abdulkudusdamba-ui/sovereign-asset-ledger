import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.asset_registry import AssetRegistry
from app.enums.asset_types import AssetType

from app.services.qr_service import generate_qr
from app.services.pdf_service_v3 import generate_certificate

def generate_sal_id():
    return f"SAL-{uuid.uuid4().hex[:12].upper()}"


def register_asset(
    db: Session,
    asset_type: AssetType,
    registry_id: int,
    owner: str,
    estimated_value: float = 0.0,
    asset_details: dict | None = None,
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
    generate_qr(registry.sal_id)

    # Prepare Certificate Data
    certificate_data = {
        "certificate_number": f"CERT-{datetime.now().strftime('%Y')}-{registry.id:06d}",
        "sal_id": registry.sal_id,
        "owner": registry.owner,
        "asset_type": registry.asset_type,
        "estimated_value": registry.estimated_value,
        "registration_date": datetime.now().strftime("%d %B %Y"),
        "asset_details": asset_details or {
            "Registry ID": registry.registry_id,
            "Status": registry.status,
        },
    }

    # Generate PDF Certificate
    generate_certificate(certificate_data)

    return registry