from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.payment_reconciliation import PaymentReconciliation
from app.schemas.payment_reconciliation import PaymentReconciliationResponse
from app.services.payment_reconciliation_service import (
    PaymentReconciliationService,
)


router = APIRouter(
    prefix="/reconciliation",
    tags=["Payment Reconciliation"],
)


@router.post(
    "/{payment_id}",
    response_model=PaymentReconciliationResponse,
)
def reconcile_payment(
    payment_id: int,
    db: Session = Depends(get_db),
):

    try:
        reconciliation = (
            PaymentReconciliationService.reconcile_payment(
                db=db,
                payment_id=payment_id,
            )
        )

        return reconciliation

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.get(
    "/",
    response_model=list[PaymentReconciliationResponse],
)
def get_reconciliations(
    db: Session = Depends(get_db),
):

    return (
        db.query(PaymentReconciliation)
        .order_by(PaymentReconciliation.id.desc())
        .all()
    )


@router.get(
    "/{reconciliation_id}",
    response_model=PaymentReconciliationResponse,
)
def get_reconciliation(
    reconciliation_id: int,
    db: Session = Depends(get_db),
):

    reconciliation = (
        db.query(PaymentReconciliation)
        .filter(
            PaymentReconciliation.id == reconciliation_id
        )
        .first()
    )

    if not reconciliation:

        raise HTTPException(
            status_code=404,
            detail="Reconciliation not found",
        )

    return reconciliation
