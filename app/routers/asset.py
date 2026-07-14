from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.database.database import get_db
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse

router = APIRouter(
    prefix="/assets",
    tags=["Assets"]
)


# Create Asset (Admin & Registrar only)
@router.post("/", response_model=AssetResponse)
def create_asset(
    asset: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "registrar"]))
):
    new_asset = Asset(
        asset_name=asset.asset_name,
        value=asset.value,
        owner=asset.owner
    )

    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)

    return new_asset


# Get All Assets (Any authenticated user)
@router.get("/", response_model=list[AssetResponse])
def get_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Asset).all()


# Get Single Asset (Any authenticated user)
@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    return asset


# Update Asset (Admin & Registrar only)
@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    updated_asset: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "registrar"]))
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    asset.asset_name = updated_asset.asset_name
    asset.value = updated_asset.value
    asset.owner = updated_asset.owner

    db.commit()
    db.refresh(asset)

    return asset


# Delete Asset (Admin only)
@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    db.delete(asset)
    db.commit()

    return {"message": "Asset deleted successfully"}