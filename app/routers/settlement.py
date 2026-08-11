from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.settlement import SettlementResponse
from app.services.settlement_service import SettlementService


router = APIRouter(
    prefix="/settlements",
    tags=["Settlements"]
)


@router.get(
    "/{payment_id}",
    response_model=SettlementResponse
)
def get_settlement_status(
    payment_id: int,
    db: Session = Depends(get_db)
):
    try:
        return SettlementService.get_settlement_status(
            db=db,
            payment_id=payment_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )


@router.post(
    "/{payment_id}/settle",
    response_model=SettlementResponse
)
def settle_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):
    try:
        return SettlementService.settle_payment(
            db=db,
            payment_id=payment_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )
