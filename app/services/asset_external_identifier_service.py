from sqlalchemy.orm import Session

from app.models.asset_external_identifier import AssetExternalIdentifier
from app.models.asset_registry import AssetRegistry
from app.services.audit_service import record_audit_event


class AssetExternalIdentifierError(Exception):
    """Base error for external asset identifier operations."""


class AssetExternalIdentifierNotFoundError(
    AssetExternalIdentifierError
):
    """Raised when an external identifier does not exist."""


class AssetRegistryNotFoundError(AssetExternalIdentifierError):
    """Raised when the referenced SAL asset does not exist."""


class AssetExternalIdentifierConflictError(
    AssetExternalIdentifierError
):
    """Raised when an active external identifier already exists."""


def _normalize(value: str) -> str:
    return value.strip().upper()


def add_external_identifier(
    db: Session,
    *,
    asset_registry_id: int,
    authority: str,
    identifier_type: str,
    identifier_value: str,
    status: str = "ACTIVE",
    source_reference: str | None = None,
    verified_at=None,
    actor_id: int | None = None,
    actor_type: str = "USER",
    source: str = "API",
    reason: str | None = None,
    reference: str | None = None,
) -> AssetExternalIdentifier:
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == asset_registry_id)
        .first()
    )

    if not asset:
        raise AssetRegistryNotFoundError(
            f"Asset Registry {asset_registry_id} was not found"
        )

    normalized_authority = _normalize(authority)
    normalized_type = _normalize(identifier_type)
    normalized_value = _normalize(identifier_value)
    normalized_status = _normalize(status)

    existing = (
        db.query(AssetExternalIdentifier)
        .filter(
            AssetExternalIdentifier.authority == normalized_authority,
            AssetExternalIdentifier.identifier_type == normalized_type,
            AssetExternalIdentifier.identifier_value == normalized_value,
            AssetExternalIdentifier.status == "ACTIVE",
        )
        .first()
    )

    if existing:
        raise AssetExternalIdentifierConflictError(
            "An active external identifier already exists for "
            f"{normalized_authority}/{normalized_type}/{normalized_value}"
        )

    identifier = AssetExternalIdentifier(
        asset_registry_id=asset_registry_id,
        authority=normalized_authority,
        identifier_type=normalized_type,
        identifier_value=normalized_value,
        status=normalized_status,
        source_reference=source_reference,
        verified_at=verified_at,
    )

    db.add(identifier)
    db.flush()

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_type=actor_type,
        action="EXTERNAL_IDENTIFIER_CREATED",
        entity_type="ASSET_EXTERNAL_IDENTIFIER",
        entity_id=identifier.id,
        asset_registry_id=asset_registry_id,
        source=source,
        reason=reason,
        reference=reference,
        result="SUCCESS",
        before_data=None,
        after_data={
            "authority": normalized_authority,
            "identifier_type": normalized_type,
            "identifier_value": normalized_value,
            "status": normalized_status,
            "source_reference": source_reference,
            "verified_at": verified_at,
        },
    )

    return identifier


def get_external_identifiers(
    db: Session,
    *,
    asset_registry_id: int,
) -> list[AssetExternalIdentifier]:
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == asset_registry_id)
        .first()
    )

    if not asset:
        raise AssetRegistryNotFoundError(
            f"Asset Registry {asset_registry_id} was not found"
        )

    return (
        db.query(AssetExternalIdentifier)
        .filter(
            AssetExternalIdentifier.asset_registry_id == asset_registry_id
        )
        .order_by(AssetExternalIdentifier.id.asc())
        .all()
    )


def get_external_identifier(
    db: Session,
    *,
    identifier_id: int,
) -> AssetExternalIdentifier:
    identifier = (
        db.query(AssetExternalIdentifier)
        .filter(AssetExternalIdentifier.id == identifier_id)
        .first()
    )

    if not identifier:
        raise AssetExternalIdentifierNotFoundError(
            f"External identifier {identifier_id} was not found"
        )

    return identifier


def find_asset_by_external_identifier(
    db: Session,
    *,
    authority: str,
    identifier_type: str,
    identifier_value: str,
) -> AssetRegistry | None:
    normalized_authority = _normalize(authority)
    normalized_type = _normalize(identifier_type)
    normalized_value = _normalize(identifier_value)

    identifier = (
        db.query(AssetExternalIdentifier)
        .filter(
            AssetExternalIdentifier.authority == normalized_authority,
            AssetExternalIdentifier.identifier_type == normalized_type,
            AssetExternalIdentifier.identifier_value == normalized_value,
            AssetExternalIdentifier.status == "ACTIVE",
        )
        .first()
    )

    if not identifier:
        return None

    return (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == identifier.asset_registry_id)
        .first()
    )


def update_external_identifier_status(
    db: Session,
    *,
    identifier_id: int,
    new_status: str,
    actor_id: int | None = None,
    actor_type: str = "USER",
    source: str = "API",
    reason: str | None = None,
    reference: str | None = None,
) -> AssetExternalIdentifier:
    identifier = get_external_identifier(
        db,
        identifier_id=identifier_id,
    )

    old_status = identifier.status
    normalized_status = _normalize(new_status)

    if old_status == normalized_status:
        raise AssetExternalIdentifierConflictError(
            f"External identifier {identifier.id} is already "
            f"in {normalized_status}"
        )

    identifier.status = normalized_status
    db.flush()

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_type=actor_type,
        action="EXTERNAL_IDENTIFIER_STATUS_CHANGED",
        entity_type="ASSET_EXTERNAL_IDENTIFIER",
        entity_id=identifier.id,
        asset_registry_id=identifier.asset_registry_id,
        source=source,
        reason=reason,
        reference=reference,
        result="SUCCESS",
        before_data={
            "status": old_status,
        },
        after_data={
            "status": normalized_status,
        },
    )

    db.refresh(identifier)

    return identifier
