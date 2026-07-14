from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.bond import Bond
from app.schemas.bond import BondCreate, BondResponse
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/bonds",
    tags=["Bonds"]
)


# Get all bonds
@router.get("/", response_model=list[BondResponse])
def get_bonds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Bond).all()


# Create a bond
@router.post("/", response_model=BondResponse)
def create_bond(
    bond: BondCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_bond = Bond(**bond.model_dump())

    db.add(new_bond)
    db.commit()
    db.refresh(new_bond)

    return new_bond


# Get one bond
@router.get("/{bond_id}", response_model=BondResponse)
def get_bond(
    bond_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bond = db.query(Bond).filter(Bond.id == bond_id).first()

    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    return bond


# Update a bond
@router.put("/{bond_id}", response_model=BondResponse)
def update_bond(
    bond_id: int,
    updated_bond: BondCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bond = db.query(Bond).filter(Bond.id == bond_id).first()

    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    for key, value in updated_bond.model_dump().items():
        setattr(bond, key, value)

    db.commit()
    db.refresh(bond)

    return bond


# Delete a bond
@router.delete("/{bond_id}")
def delete_bond(
    bond_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bond = db.query(Bond).filter(Bond.id == bond_id).first()

    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")

    db.delete(bond)
    db.commit()

    return {"message": "Bond deleted successfully"}