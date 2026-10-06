from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.models.asset_external_identifier import AssetExternalIdentifier
from app.schemas.asset_external_identifier import (
    AssetExternalIdentifierCreate,
    AssetExternalIdentifierLookupResponse,
    AssetExternalIdentifierResponse,
    AssetExternalIdentifierStatusUpdate,
)
from app.services.asset_external_identifier_service import (
    AssetExternalIdentifierConflictError,
    AssetExternalIdentifierNotFoundError,
    AssetRegistryNotFoundError,
    add_external_identifier,
    find_asset_by_external_identifier,
    get_external_identifier,
    get_external_identifiers,
    update_external_identifier_status,
)


router = APIRouter(
    prefix="/asset-external-identifiers",
    tags=["Asset External Identifiers"],
)


@router.post(
    "",
    response_model=AssetExternalIdentifierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_external_identifier(
    request: AssetExternalIdentifierCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    try:
        identifier = add_external_identifier(
            db,
            asset_registry_id=request.asset_registry_id,
            authority=request.authority,
            identifier_type=request.identifier_type,
            identifier_value=request.identifier_value,
            status=request.status,
            source_reference=request.source_reference,
            verified_at=request.verified_at,
            actor_id=current_user.id,
            actor_type="USER",
            source="API",
            reason=request.reason,
            reference=request.reference,
        )

        db.commit()
        db.refresh(identifier)

        return identifier

    except AssetRegistryNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except AssetExternalIdentifierConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/asset/{asset_registry_id}",
    response_model=list[AssetExternalIdentifierResponse],
)
def list_asset_external_identifiers(
    asset_registry_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(["admin", "registrar", "government"])
    ),
):
    try:
        return get_external_identifiers(
            db,
            asset_registry_id=asset_registry_id,
        )

    except AssetRegistryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/lookup/by-external-id",
    response_model=AssetExternalIdentifierLookupResponse,
)
def lookup_asset_by_external_identifier(
    authority: str,
    identifier_type: str,
    identifier_value: str,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(["admin", "registrar", "government"])
    ),
):
    asset = find_asset_by_external_identifier(
        db,
        authority=authority,
        identifier_type=identifier_type,
        identifier_value=identifier_value,
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active asset external identifier was not found",
        )

    normalized_authority = authority.strip().upper()
    normalized_type = identifier_type.strip().upper()
    normalized_value = identifier_value.strip().upper()

    identifier = (
        db.query(AssetExternalIdentifier)
        .filter(
            AssetExternalIdentifier.asset_registry_id == asset.id,
            AssetExternalIdentifier.authority == normalized_authority,
            AssetExternalIdentifier.identifier_type == normalized_type,
            AssetExternalIdentifier.identifier_value == normalized_value,
            AssetExternalIdentifier.status == "ACTIVE",
        )
        .first()
    )

    if identifier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active asset external identifier was not found",
        )

    return {
        "sal_id": asset.sal_id,
        "asset_registry_id": asset.id,
        "asset_type": asset.asset_type,
        "owner": asset.owner,
        "identifier": identifier,
    }


@router.get(
    "/{identifier_id}",
    response_model=AssetExternalIdentifierResponse,
)
def get_one_external_identifier(
    identifier_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(["admin", "registrar", "government"])
    ),
):
    try:
        return get_external_identifier(
            db,
            identifier_id=identifier_id,
        )

    except AssetExternalIdentifierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{identifier_id}/status",
    response_model=AssetExternalIdentifierResponse,
)
def change_external_identifier_status(
    identifier_id: int,
    request: AssetExternalIdentifierStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    try:
        identifier = update_external_identifier_status(
            db,
            identifier_id=identifier_id,
            new_status=request.status,
            actor_id=current_user.id,
            actor_type="USER",
            source="API",
            reason=request.reason,
            reference=request.reference,
        )

        db.commit()
        db.refresh(identifier)

        return identifier

    except AssetExternalIdentifierNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except AssetExternalIdentifierConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
