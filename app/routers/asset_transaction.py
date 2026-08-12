from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.asset_transaction import (
    AssetTransactionCreate,
    AssetTransactionResponse
)
from app.services.asset_transaction_service import (
    AssetTransactionService
)


router = APIRouter(
    prefix="/asset-transactions",
    tags=["Asset Transactions"]
)


@router.post(
    "/",
    response_model=AssetTransactionResponse
)
def create_asset_transaction(
    request: AssetTransactionCreate,
    db: Session = Depends(get_db)
):
    return AssetTransactionService.create_transaction(
        db=db,
        asset_id=request.asset_id,
        asset_type=request.asset_type,
        transaction_type=request.transaction_type,
        seller=request.seller,
        buyer=request.buyer,
        amount=request.amount,
        currency=request.currency,
        description=request.description
    )


@router.get(
    "/",
    response_model=list[AssetTransactionResponse]
)
def get_asset_transactions(
    db: Session = Depends(get_db)
):
    return AssetTransactionService.list_transactions(db)


@router.get(
    "/{transaction_id}",
    response_model=AssetTransactionResponse
)
def get_asset_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    transaction = AssetTransactionService.get_transaction(
        db=db,
        transaction_id=transaction_id
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Asset transaction not found"
        )

    return transaction


@router.patch(
    "/{transaction_id}/status",
    response_model=AssetTransactionResponse
)
def update_asset_transaction_status(
    transaction_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    transaction = AssetTransactionService.update_status(
        db=db,
        transaction_id=transaction_id,
        status=status
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Asset transaction not found"
        )

    return transaction
@router.patch(
    "/{transaction_id}/payment/{payment_id}",
    response_model=AssetTransactionResponse
)
def attach_payment_to_asset_transaction(
    transaction_id: int,
    payment_id: int,
    db: Session = Depends(get_db)
):
    try:
        transaction = AssetTransactionService.attach_payment(
            db=db,
            transaction_id=transaction_id,
            payment_id=payment_id
        )

        if not transaction:
            raise HTTPException(
                status_code=404,
                detail="Asset transaction not found"
            )

        return transaction

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
