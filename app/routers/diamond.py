from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.diamond import Diamond
from app.models.user import User
from app.schemas.diamond import DiamondCreate, DiamondResponse
from app.core.auth import get_current_user

router = APIRouter(
    prefix="/diamonds",
    tags=["Diamonds"]
)


@router.get("/", response_model=list[DiamondResponse])
def get_diamonds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Diamond).all()


@router.post("/", response_model=DiamondResponse)
def create_diamond(
    diamond: DiamondCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_diamond = Diamond(**diamond.model_dump())
    db.add(new_diamond)
    db.commit()
    db.refresh(new_diamond)
    return new_diamond


@router.get("/{diamond_id}", response_model=DiamondResponse)
def get_diamond(
    diamond_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    diamond = db.query(Diamond).filter(Diamond.id == diamond_id).first()

    if not diamond:
        raise HTTPException(status_code=404, detail="Diamond not found")

    return diamond


@router.put("/{diamond_id}", response_model=DiamondResponse)
def update_diamond(
    diamond_id: int,
    diamond_data: DiamondCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    diamond = db.query(Diamond).filter(Diamond.id == diamond_id).first()

    if not diamond:
        raise HTTPException(status_code=404, detail="Diamond not found")

    for key, value in diamond_data.model_dump().items():
        setattr(diamond, key, value)

    db.commit()
    db.refresh(diamond)

    return diamond


@router.delete("/{diamond_id}")
def delete_diamond(
    diamond_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    diamond = db.query(Diamond).filter(Diamond.id == diamond_id).first()

    if not diamond:
        raise HTTPException(status_code=404, detail="Diamond not found")

    db.delete(diamond)
    db.commit()

    return {"message": "Diamond deleted successfully"}