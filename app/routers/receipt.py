from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.receipt import Receipt
from app.schemas.receipt import ReceiptResponse

router = APIRouter(
    prefix="/receipts",
    tags=["Receipts"]
)


@router.get(
    "/",
    response_model=list[ReceiptResponse]
)
def get_receipts(
    db: Session = Depends(get_db)
):
    return db.query(Receipt).all()


@router.get(
    "/{receipt_id}",
    response_model=ReceiptResponse
)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db)
):

    receipt = (
        db.query(Receipt)
        .filter(Receipt.id == receipt_id)
        .first()
    )

    if not receipt:
        raise HTTPException(
            status_code=404,
            detail="Receipt not found"
        )

    return receipt
