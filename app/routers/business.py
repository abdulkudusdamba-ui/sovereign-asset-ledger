from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessResponse
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/businesses",
    tags=["Businesses"]
)


@router.get("/", response_model=list[BusinessResponse])
def get_businesses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Business).all()


@router.post("/", response_model=BusinessResponse)
def create_business(
    business: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_business = Business(**business.model_dump())

    db.add(new_business)
    db.commit()
    db.refresh(new_business)

    return new_business


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    return business


@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(
    business_id: int,
    updated_business: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    for key, value in updated_business.model_dump().items():
        setattr(business, key, value)

    db.commit()
    db.refresh(business)

    return business


@router.delete("/{business_id}")
def delete_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    db.delete(business)
    db.commit()

    return {"message": "Business deleted successfully"}