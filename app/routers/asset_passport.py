import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.asset_passport import AssetPassport
from app.models.asset_registry import AssetRegistry
from app.schemas.asset_passport import (
    AssetPassportCreate,
    AssetPassportResponse,
)


router = APIRouter(
    prefix="/passport",
    tags=["Asset Passport"]
)


def generate_passport_id() -> str:
    return f"SAL-PASSPORT-{uuid.uuid4().hex[:12].upper()}"


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
            detail="SAL asset identity not found"
        )

    existing = (
        db.query(AssetPassport)
        .filter(AssetPassport.asset_registry_id == asset.id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Asset Passport already exists for this SAL asset"
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
            detail="Asset Passport could not be created because the asset already has a Passport"
        )

    return record


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
            detail="SAL asset identity not found"
        )

    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.asset_registry_id == asset.id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found for this SAL asset"
        )

    return passport
