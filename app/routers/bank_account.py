from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.bank_account import BankAccount
from app.schemas.bank_account import (
    BankAccountCreate,
    BankAccountResponse,
)
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/bank-accounts",
    tags=["Bank Accounts"]
)


@router.get("/", response_model=list[BankAccountResponse])
def get_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(BankAccount).all()


@router.post("/", response_model=BankAccountResponse)
def create_bank_account(
    bank_account: BankAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_account = BankAccount(**bank_account.dict())

    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    return new_account


@router.get("/{account_id}", response_model=BankAccountResponse)
def get_bank_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()

    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    return account


@router.put("/{account_id}", response_model=BankAccountResponse)
def update_bank_account(
    account_id: int,
    updated: BankAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()

    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    for key, value in updated.dict().items():
        setattr(account, key, value)

    db.commit()
    db.refresh(account)

    return account


@router.delete("/{account_id}")
def delete_bank_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()

    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    db.delete(account)
    db.commit()

    return {"message": "Bank account deleted successfully"}