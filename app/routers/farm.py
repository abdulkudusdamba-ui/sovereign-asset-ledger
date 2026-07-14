from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmResponse
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/farms",
    tags=["Farms"]
)


@router.get("/", response_model=list[FarmResponse])
def get_farms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Farm).all()


@router.post("/", response_model=FarmResponse)
def create_farm(
    farm: FarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_farm = Farm(**farm.model_dump())
    db.add(new_farm)
    db.commit()
    db.refresh(new_farm)
    return new_farm


@router.get("/{farm_id}", response_model=FarmResponse)
def get_farm(
    farm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    return farm


@router.put("/{farm_id}", response_model=FarmResponse)
def update_farm(
    farm_id: int,
    updated: FarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    for key, value in updated.model_dump().items():
        setattr(farm, key, value)

    db.commit()
    db.refresh(farm)

    return farm


@router.delete("/{farm_id}")
def delete_farm(
    farm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()

    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    db.delete(farm)
    db.commit()

    return {"message": "Farm deleted successfully"}