import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.asset_passport import AssetPassport
from app.models.asset_registry import AssetRegistry
from app.schemas.asset_passport import AssetPassportCreate, AssetPassportResponse
from app.services.passport_lifecycle_service import (
    PassportLifecycleTransitionError,
    PassportNotFoundError,
    transition_passport_lifecycle,
)


router = APIRouter(
    prefix="/passport",
    tags=["Asset Passport"],
)


class PassportLifecycleUpdate(BaseModel):
    lifecycle_state: str

    model_config = ConfigDict(extra="forbid")


def generate_passport_id() -> str:
    return f"SAL-PASSPORT-{uuid.uuid4().hex[:12].upper()}"


def build_passport_response(
    passport: AssetPassport,
    asset: AssetRegistry,
) -> dict:
    return {
        "id": passport.id,
        "passport_id": passport.passport_id,
        "asset_registry_id": passport.asset_registry_id,
        "sal_id": asset.sal_id,
        "asset_type": asset.asset_type,
        "owner": asset.owner,
        "estimated_value": asset.estimated_value,
        "asset_status": asset.status,
        "status": passport.status,
        "lifecycle_state": passport.lifecycle_state,
        "created_at": passport.created_at,
        "updated_at": passport.updated_at,
    }


@router.post(
    "/{sal_id}",
    response_model=AssetPassportResponse,
    status_code=201,
)
def create_passport(
    sal_id: str,
    passport: AssetPassportCreate,
    db: Session = Depends(get_db),
):
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="SAL asset identity not found",
        )

    existing = (
        db.query(AssetPassport)
        .filter(AssetPassport.asset_registry_id == asset.id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Asset Passport already exists for this SAL asset",
        )

    record = AssetPassport(
        passport_id=generate_passport_id(),
        asset_registry_id=asset.id,
        status="ACTIVE",
        lifecycle_state="REGISTERED",
    )

    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Asset Passport could not be created because the asset already has a Passport",
        )

    return build_passport_response(record, asset)


@router.get(
    "/{sal_id}",
    response_model=AssetPassportResponse,
)
def get_passport(
    sal_id: str,
    db: Session = Depends(get_db),
):
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="SAL asset identity not found",
        )

    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.asset_registry_id == asset.id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found for this SAL asset",
        )

    return build_passport_response(passport, asset)


@router.patch(
    "/{passport_id}/lifecycle",
    response_model=AssetPassportResponse,
)
def update_passport_lifecycle(
    passport_id: int,
    payload: PassportLifecycleUpdate,
    db: Session = Depends(get_db),
):
    try:
        passport = transition_passport_lifecycle(
            db=db,
            passport_id=passport_id,
            new_state=payload.lifecycle_state,
        )

        db.commit()
        db.refresh(passport)

    except PassportNotFoundError:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail=f"Asset Passport {passport_id} not found",
        )

    except PassportLifecycleTransitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == passport.asset_registry_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=409,
            detail="Asset Passport exists, but its linked SAL asset identity was not found",
        )

    return build_passport_response(passport, asset)
