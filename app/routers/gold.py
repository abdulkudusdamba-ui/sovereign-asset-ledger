from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.gold import Gold
from app.models.user import User
from app.schemas.gold import GoldCreate, GoldResponse
from app.core.auth import get_current_user

router = APIRouter(
    prefix="/gold",
    tags=["Gold"]
)


@router.get("/", response_model=list[GoldResponse])
def get_gold(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Gold).all()


@router.post("/", response_model=GoldResponse)
def create_gold(
    gold: GoldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_gold = Gold(**gold.model_dump())
    db.add(new_gold)
    db.commit()
    db.refresh(new_gold)
    return new_gold


@router.get("/{gold_id}", response_model=GoldResponse)
def get_gold_by_id(
    gold_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gold = db.query(Gold).filter(Gold.id == gold_id).first()

    if not gold:
        raise HTTPException(status_code=404, detail="Gold not found")

    return gold


@router.put("/{gold_id}", response_model=GoldResponse)
def update_gold(
    gold_id: int,
    gold_data: GoldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gold = db.query(Gold).filter(Gold.id == gold_id).first()

    if not gold:
        raise HTTPException(status_code=404, detail="Gold not found")

    for key, value in gold_data.model_dump().items():
        setattr(gold, key, value)

    db.commit()
    db.refresh(gold)

    return gold


@router.delete("/{gold_id}")
def delete_gold(
    gold_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gold = db.query(Gold).filter(Gold.id == gold_id).first()

    if not gold:
        raise HTTPException(status_code=404, detail="Gold not found")

    db.delete(gold)
    db.commit()

    return {"message": "Gold deleted successfully"}