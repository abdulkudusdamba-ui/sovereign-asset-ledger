from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.intellectual_property import IntellectualProperty
from app.schemas.intellectual_property import (
    IntellectualPropertyCreate,
    IntellectualPropertyResponse,
)
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/intellectual-property",
    tags=["Intellectual Property"]
)


@router.get("/", response_model=list[IntellectualPropertyResponse])
def get_all_ip(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(IntellectualProperty).all()


@router.post("/", response_model=IntellectualPropertyResponse)
def create_ip(
    ip: IntellectualPropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_ip = IntellectualProperty(**ip.model_dump())
    db.add(new_ip)
    db.commit()
    db.refresh(new_ip)
    return new_ip


@router.get("/{ip_id}", response_model=IntellectualPropertyResponse)
def get_ip(
    ip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ip = db.query(IntellectualProperty).filter(
        IntellectualProperty.id == ip_id
    ).first()

    if not ip:
        raise HTTPException(status_code=404, detail="Record not found")

    return ip


@router.put("/{ip_id}", response_model=IntellectualPropertyResponse)
def update_ip(
    ip_id: int,
    updated: IntellectualPropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ip = db.query(IntellectualProperty).filter(
        IntellectualProperty.id == ip_id
    ).first()

    if not ip:
        raise HTTPException(status_code=404, detail="Record not found")

    for key, value in updated.model_dump().items():
        setattr(ip, key, value)

    db.commit()
    db.refresh(ip)

    return ip


@router.delete("/{ip_id}")
def delete_ip(
    ip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ip = db.query(IntellectualProperty).filter(
        IntellectualProperty.id == ip_id
    ).first()

    if not ip:
        raise HTTPException(status_code=404, detail="Record not found")

    db.delete(ip)
    db.commit()

    return {"message": "Intellectual property deleted successfully"}