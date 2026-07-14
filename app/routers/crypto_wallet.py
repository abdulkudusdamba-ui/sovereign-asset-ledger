from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.crypto_wallet import CryptoWallet
from app.schemas.crypto_wallet import (
    CryptoWalletCreate,
    CryptoWalletResponse,
)
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/crypto-wallets",
    tags=["Crypto Wallets"]
)


@router.get("/", response_model=list[CryptoWalletResponse])
def get_wallets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(CryptoWallet).all()


@router.post("/", response_model=CryptoWalletResponse)
def create_wallet(
    wallet: CryptoWalletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_wallet = CryptoWallet(**wallet.model_dump())

    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)

    return new_wallet


@router.get("/{wallet_id}", response_model=CryptoWalletResponse)
def get_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = db.query(CryptoWallet).filter(
        CryptoWallet.id == wallet_id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return wallet


@router.put("/{wallet_id}", response_model=CryptoWalletResponse)
def update_wallet(
    wallet_id: int,
    updated_wallet: CryptoWalletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = db.query(CryptoWallet).filter(
        CryptoWallet.id == wallet_id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    for key, value in updated_wallet.model_dump().items():
        setattr(wallet, key, value)

    db.commit()
    db.refresh(wallet)

    return wallet


@router.delete("/{wallet_id}")
def delete_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wallet = db.query(CryptoWallet).filter(
        CryptoWallet.id == wallet_id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    db.delete(wallet)
    db.commit()

    return {"message": "Wallet deleted successfully"}