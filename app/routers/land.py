from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.database.database import get_db

from app.models.land import Land
from app.models.user import User

from app.schemas.land import LandCreate, LandResponse

from app.services.asset_service import register_asset
from app.enums.asset_types import AssetType

router = APIRouter(
    prefix="/lands",
    tags=["Land Registry"]
)


# Create Land (Admin & Registrar)
@router.post("/", response_model=LandResponse)
def create_land(
    land: LandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "registrar"]))
):
    new_land = Land(**land.model_dump())

    db.add(new_land)
    db.commit()
    db.refresh(new_land)

    # Register in the SAL Master Registry
    register_asset(
        db=db,
        asset_type=AssetType.LAND,
        registry_id=new_land.id,
        owner=new_land.owner_name,
        estimated_value=new_land.estimated_value,
    )

    return new_land


# Get All Lands (Authenticated Users)
@router.get("/", response_model=list[LandResponse])
def get_lands(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Land).all()


# Get Single Land
@router.get("/{land_id}", response_model=LandResponse)
def get_land(
    land_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    land = db.query(Land).filter(Land.id == land_id).first()

    if land is None:
        raise HTTPException(
            status_code=404,
            detail="Land not found"
        )

    return land


# Update Land (Admin & Registrar)
@router.put("/{land_id}", response_model=LandResponse)
def update_land(
    land_id: int,
    updated_land: LandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "registrar"]))
):
    land = db.query(Land).filter(Land.id == land_id).first()

    if land is None:
        raise HTTPException(
            status_code=404,
            detail="Land not found"
        )

    for key, value in updated_land.model_dump().items():
        setattr(land, key, value)

    db.commit()
    db.refresh(land)

    return land


# Delete Land (Admin only)
@router.delete("/{land_id}")
def delete_land(
    land_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    land = db.query(Land).filter(Land.id == land_id).first()

    if land is None:
        raise HTTPException(
            status_code=404,
            detail="Land not found"
        )

    db.delete(land)
    db.commit()

    return {"message": "Land deleted successfully"}


# Approve Land (Admin only)
@router.put("/{land_id}/approve")
def approve_land(
    land_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    land = db.query(Land).filter(Land.id == land_id).first()

    if land is None:
        raise HTTPException(
            status_code=404,
            detail="Land not found"
        )

    land.approval_status = "Approved"

    db.commit()
    db.refresh(land)

    return {
        "message": "Land approved successfully",
        "land": land
    }


# Reject Land (Admin only)
@router.put("/{land_id}/reject")
def reject_land(
    land_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    land = db.query(Land).filter(Land.id == land_id).first()

    if land is None:
        raise HTTPException(
            status_code=404,
            detail="Land not found"
        )

    land.approval_status = "Rejected"

    db.commit()
    db.refresh(land)

    return {
        "message": "Land rejected successfully",
        "land": land
    }