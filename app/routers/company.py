from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyResponse
from app.core.auth import get_current_user

router = APIRouter(
    prefix="/companies",
    tags=["Companies"]
)


@router.get("/", response_model=list[CompanyResponse])
def get_companies(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return db.query(Company).all()


@router.post("/", response_model=CompanyResponse)
def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_company = Company(**company.dict())

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    return new_company


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return company


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    updated: CompanyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for key, value in updated.dict().items():
        setattr(company, key, value)

    db.commit()
    db.refresh(company)

    return company


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    db.delete(company)
    db.commit()

    return {"message": "Company deleted successfully"}