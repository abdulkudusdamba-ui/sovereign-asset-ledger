from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.insurance import Insurance
from app.schemas.insurance import InsuranceCreate, InsuranceResponse

router = APIRouter(
    prefix="/insurance",
    tags=["Insurance"]
)


@router.get("/", response_model=list[InsuranceResponse])
def get_insurance(db: Session = Depends(get_db)):
    return db.query(Insurance).all()


@router.post("/", response_model=InsuranceResponse)
def create_insurance(data: InsuranceCreate, db: Session = Depends(get_db)):
    insurance = Insurance(**data.dict())
    db.add(insurance)
    db.commit()
    db.refresh(insurance)
    return insurance


@router.get("/{insurance_id}", response_model=InsuranceResponse)
def get_insurance_by_id(insurance_id: int, db: Session = Depends(get_db)):
    insurance = db.query(Insurance).filter(Insurance.id == insurance_id).first()

    if not insurance:
        raise HTTPException(status_code=404, detail="Insurance not found")

    return insurance


@router.put("/{insurance_id}", response_model=InsuranceResponse)
def update_insurance(
    insurance_id: int,
    data: InsuranceCreate,
    db: Session = Depends(get_db)
):
    insurance = db.query(Insurance).filter(
        Insurance.id == insurance_id
    ).first()

    if not insurance:
        raise HTTPException(status_code=404, detail="Insurance not found")

    for key, value in data.dict().items():
        setattr(insurance, key, value)

    db.commit()
    db.refresh(insurance)

    return insurance


@router.delete("/{insurance_id}")
def delete_insurance(insurance_id: int, db: Session = Depends(get_db)):
    insurance = db.query(Insurance).filter(
        Insurance.id == insurance_id
    ).first()

    if not insurance:
        raise HTTPException(status_code=404, detail="Insurance not found")

    db.delete(insurance)
    db.commit()

    return {"message": "Insurance deleted successfully"}