from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.models.asset_registry import AssetRegistry

from app.schemas.asset_registry import (
    AssetRegistryCreate,
    AssetRegistryResponse
)

router = APIRouter(
    prefix="/registry",
    tags=["Master Registry"]
)


@router.get("/", response_model=list[AssetRegistryResponse])
def get_registry(db: Session = Depends(get_db)):
    return db.query(AssetRegistry).all()


@router.post("/", response_model=AssetRegistryResponse)
def create_registry(
    registry: AssetRegistryCreate,
    db: Session = Depends(get_db)
):
    record = AssetRegistry(**registry.model_dump())

    db.add(record)

    db.commit()

    db.refresh(record)

    return record