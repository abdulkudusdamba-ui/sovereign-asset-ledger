from sqlalchemy.orm import Session

from app.models.asset_external_identifier import AssetExternalIdentifier
from app.models.asset_registry import AssetRegistry
from app.models.government_verification import GovernmentVerification
from app.models.vehicle import Vehicle


class VehicleIdentityError(Exception):
    """Base error for vehicle identity resolution."""


class VehicleIdentityNotFoundError(VehicleIdentityError):
    """Raised when the requested SAL vehicle identity does not exist."""


class VehicleIdentityConflictError(VehicleIdentityError):
    """Raised when the SAL identity points to an invalid vehicle record."""


def get_vehicle_identity_by_sal_id(
    db: Session,
    *,
    sal_id: str,
) -> dict:
    """
    Resolve a SAL Vehicle identity into its intrinsic identity,
    SAL identity, external authority identifiers, and latest
    government verification state.

    This service is read-only.

    Presence of an external identifier does not imply government
    verification. Verification status is reported separately.
    """

    asset = (
        db.query(AssetRegistry)
        .filter(
            AssetRegistry.sal_id == sal_id,
            AssetRegistry.asset_type.ilike("VEHICLE"),
        )
        .first()
    )

    if not asset:
        raise VehicleIdentityNotFoundError(
            f"SAL Vehicle identity '{sal_id}' was not found"
        )

    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == asset.registry_id)
        .first()
    )

    if not vehicle:
        raise VehicleIdentityConflictError(
            "SAL registry identity exists, but the linked vehicle "
            "record was not found"
        )

    external_identifiers = (
        db.query(AssetExternalIdentifier)
        .filter(
            AssetExternalIdentifier.asset_registry_id == asset.id,
            AssetExternalIdentifier.status == "ACTIVE",
        )
        .order_by(AssetExternalIdentifier.id.asc())
        .all()
    )

    latest_government_verification = (
        db.query(GovernmentVerification)
        .filter(
            GovernmentVerification.asset_registry_id == asset.id
        )
        .order_by(
            GovernmentVerification.id.desc()
        )
        .first()
    )

    if latest_government_verification:
        government_verification = {
            "status": latest_government_verification.status,
            "authority": latest_government_verification.authority,
            "reference_number": (
                latest_government_verification.reference_number
            ),
            "verified_by": latest_government_verification.verified_by,
            "verified_at": latest_government_verification.verified_at,
            "notes": latest_government_verification.notes,
        }
    else:
        government_verification = {
            "status": (
                asset.government_verification
                or "NOT_VERIFIED"
            ),
            "authority": None,
            "reference_number": None,
            "verified_by": None,
            "verified_at": None,
            "notes": None,
        }

    return {
        "sal_id": asset.sal_id,
        "asset_registry_id": asset.id,
        "vehicle_id": vehicle.id,
        "identity": {
            "vin": vehicle.vin,
            "chassis_number": vehicle.chassis_number,
            "engine_number": vehicle.engine_number,
            "registration_number": vehicle.registration_number,
        },
        "vehicle": {
            "manufacturer": vehicle.manufacturer,
            "model": vehicle.model,
            "year": vehicle.year,
            "color": vehicle.color,
            "status": vehicle.status,
        },
        "sal": {
            "status": asset.status,
            "verification": asset.sal_verification or "VERIFIED",
        },
        "external_identifiers": external_identifiers,
        "government_verification": government_verification,
    }
