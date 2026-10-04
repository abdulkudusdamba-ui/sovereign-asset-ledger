import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.asset_registry import AssetRegistry
from app.enums.asset_types import AssetType

from app.services.qr_service import generate_qr
from app.services.pdf_service_v3 import generate_certificate


def generate_sal_id() -> str:
    """
    Generate a new SAL asset identity.

    Identity rules:
    - Generated only by the SAL server.
    - Existing SAL IDs are never regenerated.
    - New IDs use 96 bits of UUID randomness.
    - The database unique constraint remains the final
      protection against duplicate identities.
    """
    return f"SAL-{uuid.uuid4().hex[:24].upper()}"


def create_asset_registry_record(
    db: Session,
    asset_type: AssetType,
    registry_id: int,
    owner: str,
    estimated_value: float = 0.0,
    status: str = "Active",
):
    """
    Create a SAL Master Registry record.

    IMPORTANT:
    - This function does NOT commit.
    - The caller controls the transaction.
    - This allows an underlying asset and its SAL identity
      to be committed atomically.
    """

    registry = AssetRegistry(
        sal_id=generate_sal_id(),
        asset_type=asset_type.value,
        registry_id=registry_id,
        owner=owner,
        estimated_value=estimated_value,
        status=status,

        sal_verification="VERIFIED",
        government_verification="NOT_VERIFIED",
        blockchain_status="PENDING",
    )

    db.add(registry)

    # Assign the database ID without committing.
    db.flush()

    return registry


def generate_asset_artifacts(
    registry: AssetRegistry,
    asset_details: dict | None = None,
):
    """
    Generate external SAL artifacts after the database transaction
    has successfully committed.

    These artifacts include:
    - QR code
    - SAL certificate PDF

    They intentionally happen AFTER database commit because they
    write files outside the database transaction.
    """

    # Generate QR Code
    generate_qr(registry.sal_id)

    # Prepare Certificate Data
    certificate_data = {
        "certificate_number": (
            f"CERT-{datetime.now().strftime('%Y')}-{registry.id:06d}"
        ),
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


def register_asset(
    db: Session,
    asset_type: AssetType,
    registry_id: int,
    owner: str,
    estimated_value: float = 0.0,
    asset_details: dict | None = None,
):
    """
    Backward-compatible SAL asset registration helper.

    This function is still used by existing routes such as Land.

    It:
    1. Creates the SAL Master Registry record.
    2. Commits it.
    3. Refreshes it.
    4. Generates QR/certificate artifacts.

    Vehicle registration uses create_asset_registry_record()
    directly so the Vehicle + SAL identity can share one
    atomic database transaction.
    """

    registry = create_asset_registry_record(
        db=db,
        asset_type=asset_type,
        registry_id=registry_id,
        owner=owner,
        estimated_value=estimated_value,
    )

    db.commit()
    db.refresh(registry)

    generate_asset_artifacts(
        registry=registry,
        asset_details=asset_details,
    )

    return registry
