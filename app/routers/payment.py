from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.receipt import Receipt

from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    PaymentStatusUpdate,
)

from app.services.payment_service import PaymentService
from app.services.receipt_service import ReceiptService
from app.services.payment_audit_service import PaymentAuditService

from app.providers.provider_factory import PaymentProviderFactory


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


# ==========================================================
# CREATE PAYMENT
# ==========================================================

@router.post(
    "/",
    response_model=PaymentResponse
)
def create_payment(
    request: PaymentCreate,
    db: Session = Depends(get_db)
):

    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == request.invoice_id)
        .first()
    )

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found"
        )

    payment = Payment(
        invoice_id=request.invoice_id,
        transaction_id=PaymentService.generate_transaction_id(),
        provider=request.provider,
        payment_method=request.payment_method,
        currency=request.currency,
        amount=request.amount,
        status="PENDING"
    )

    provider = PaymentProviderFactory.get_provider("sandbox")
    provider.initialize_payment(payment)

    db.add(payment)
    db.commit()
    db.refresh(payment)

    PaymentAuditService.log(
        db=db,
        payment_id=payment.id,
        event="PAYMENT_CREATED",
        description="Payment initialized."
    )

    db.commit()

    return payment


# ==========================================================
# GET ALL PAYMENTS
# ==========================================================

@router.get(
    "/",
    response_model=list[PaymentResponse]
)
def get_payments(
    db: Session = Depends(get_db)
):
    return db.query(Payment).all()


# ==========================================================
# GET SINGLE PAYMENT
# ==========================================================

@router.get(
    "/{payment_id}",
    response_model=PaymentResponse
)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )

    return payment


# ==========================================================
# UPDATE PAYMENT STATUS
# ==========================================================

@router.patch(
    "/{payment_id}/status",
    response_model=PaymentResponse
)
def update_payment_status(
    payment_id: int,
    request: PaymentStatusUpdate,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )

    payment.status = request.status

    if request.provider_reference:
        payment.provider_reference = request.provider_reference

    if request.status == "PAID":

        payment.paid_at = datetime.utcnow()

        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == payment.invoice_id)
            .first()
        )

        if invoice:

            invoice.status = "PAID"
            invoice.paid_at = payment.paid_at

            existing_receipt = (
                db.query(Receipt)
                .filter(Receipt.payment_id == payment.id)
                .first()
            )

            if existing_receipt is None:

                receipt = Receipt(
                    payment_id=payment.id,
                    receipt_number=ReceiptService.generate_receipt_number(db),
                    customer=invoice.customer,
                    currency=invoice.currency,
                    amount=payment.amount
                )

                db.add(receipt)

                PaymentAuditService.log(
                    db=db,
                    payment_id=payment.id,
                    event="RECEIPT_GENERATED",
                    description=f"Receipt {receipt.receipt_number} generated."
                )

        PaymentAuditService.log(
            db=db,
            payment_id=payment.id,
            event="PAYMENT_PAID",
            description="Payment marked as PAID."
        )

    elif request.status == "FAILED":

        PaymentAuditService.log(
            db=db,
            payment_id=payment.id,
            event="PAYMENT_FAILED",
            description="Payment failed."
        )

    elif request.status == "REFUNDED":

        PaymentAuditService.log(
            db=db,
            payment_id=payment.id,
            event="PAYMENT_REFUNDED",
            description="Payment refunded."
        )

    db.commit()
    db.refresh(payment)

    return payment