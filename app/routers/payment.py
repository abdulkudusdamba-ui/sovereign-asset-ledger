from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.payment_audit import PaymentAudit

from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
)

from app.services.payment_service import PaymentService
from app.services.payment_state_service import PaymentStateService
from app.services.payment_audit_service import PaymentAuditService
from app.services.payment_reconciliation_service import (
    PaymentReconciliationService,
)
from app.services.settlement_service import SettlementService

from app.providers.provider_factory import PaymentProviderFactory


router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


@router.post(
    "/",
    response_model=PaymentResponse
)
def create_payment(
    request: PaymentCreate,
    db: Session = Depends(get_db)
):
    """
    Create a pending payment.

    The client requests a payment.

    The client does NOT determine whether the payment
    becomes PAID.
    """

    try:
        invoice = (
            db.query(Invoice)
            .filter(
                Invoice.id == request.invoice_id
            )
            .first()
        )

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        if not request.currency:
            raise HTTPException(
                status_code=400,
                detail="Payment currency is required"
            )

        if (
            invoice.currency
            and request.currency.upper()
            != invoice.currency.upper()
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Payment currency does not match "
                    "invoice currency"
                )
            )

        requested_amount = float(request.amount)
        invoice_total = float(invoice.total)

        if requested_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Payment amount must be greater than zero"
            )

        if abs(
            requested_amount - invoice_total
        ) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Payment amount must match "
                    "invoice total"
                )
            )

        payment = PaymentService.create_payment(
            db=db,
            invoice_id=invoice.id,
            provider=request.provider,
            payment_method=request.payment_method,
            commit=False
        )

        provider = PaymentProviderFactory.get_provider(
            request.provider
        )

        provider.initialize_payment(payment)

        existing_created_audit = (
            db.query(PaymentAudit)
            .filter(
                PaymentAudit.payment_id == payment.id,
                PaymentAudit.event == "PAYMENT_CREATED"
            )
            .first()
        )

        if existing_created_audit is None:
            PaymentAuditService.log(
                db=db,
                payment_id=payment.id,
                event="PAYMENT_CREATED",
                description=(
                    f"Payment initialized using provider "
                    f"{request.provider}."
                )
            )

        db.commit()
        db.refresh(payment)

        return payment

    except HTTPException:
        db.rollback()
        raise

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create payment"
        )


@router.get(
    "/",
    response_model=list[PaymentResponse]
)
def get_payments(
    db: Session = Depends(get_db)
):
    return (
        db.query(Payment)
        .order_by(Payment.id.desc())
        .all()
    )


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
        .filter(
            Payment.id == payment_id
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )

    return payment


@router.post(
    "/{payment_id}/verify",
    response_model=PaymentResponse
)
def verify_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):
    try:
        payment = (
            db.query(Payment)
            .filter(
                Payment.id == payment_id
            )
            .first()
        )

        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )

        provider = PaymentProviderFactory.get_provider(
            payment.provider
        )

        provider_result = provider.verify_payment(
            payment.transaction_id
        )

        if not isinstance(provider_result, dict):
            raise ValueError(
                "Invalid payment provider response"
            )

        if provider_result.get("success") is False:
            raise ValueError(
                "Payment provider verification failed"
            )

        provider_transaction_id = provider_result.get(
            "transaction_id"
        )

        if not provider_transaction_id:
            raise ValueError(
                "Payment provider response is missing transaction_id"
            )

        if provider_transaction_id != payment.transaction_id:
            raise ValueError(
                "Payment provider transaction ID does not match payment"
            )

        provider_status = PaymentStateService.normalize_status(
            provider_result.get("status")
        )

        PaymentStateService.transition(
            db=db,
            payment_id=payment.id,
            new_status=provider_status,
            commit=False
        )

        provider_reference = provider_result.get(
            "provider_reference"
        )

        if provider_reference:
            payment.provider_reference = provider_reference

        # =====================================================
        # PAID
        # =====================================================

        if provider_status == "PAID":

            if payment.paid_at is None:
                payment.paid_at = datetime.utcnow()

            invoice = (
                db.query(Invoice)
                .filter(
                    Invoice.id == payment.invoice_id
                )
                .first()
            )

            if not invoice:
                raise ValueError(
                    "Invoice not found"
                )

            if payment.amount != invoice.total:
                raise ValueError(
                    "Payment amount does not match invoice total"
                )

            if payment.currency.upper() != invoice.currency.upper():
                raise ValueError(
                    "Payment currency does not match invoice currency"
                )

            invoice.status = "PAID"
            invoice.paid_at = payment.paid_at

            # -------------------------------------------------
            # Receipt audit
            # -------------------------------------------------

            existing_receipt = (
                db.query(PaymentAudit)
                .filter(
                    PaymentAudit.payment_id == payment.id,
                    PaymentAudit.event == "RECEIPT_GENERATED"
                )
                .first()
            )

            if existing_receipt is None:
                PaymentAuditService.log(
                    db=db,
                    payment_id=payment.id,
                    event="RECEIPT_GENERATED",
                    description=(
                        "Receipt generated after successful "
                        "payment verification."
                    )
                )

            # -------------------------------------------------
            # Payment paid audit
            # -------------------------------------------------

            existing_paid_audit = (
                db.query(PaymentAudit)
                .filter(
                    PaymentAudit.payment_id == payment.id,
                    PaymentAudit.event == "PAYMENT_PAID"
                )
                .first()
            )

            if existing_paid_audit is None:
                PaymentAuditService.log(
                    db=db,
                    payment_id=payment.id,
                    event="PAYMENT_PAID",
                    description=(
                        "Payment verified as PAID by "
                        "the payment provider."
                    )
                )

            # -------------------------------------------------
            # Reconciliation
            # -------------------------------------------------

            PaymentReconciliationService.reconcile_payment(
                db=db,
                payment_id=payment.id,
                commit=False
            )

            # -------------------------------------------------
            # Settlement
            # -------------------------------------------------

            SettlementService.settle_payment(
                db=db,
                payment_id=payment.id,
                commit=False
            )

        # =====================================================
        # FAILED
        # =====================================================

        elif provider_status == "FAILED":

            existing_failed_audit = (
                db.query(PaymentAudit)
                .filter(
                    PaymentAudit.payment_id == payment.id,
                    PaymentAudit.event == "PAYMENT_FAILED"
                )
                .first()
            )

            if existing_failed_audit is None:
                PaymentAuditService.log(
                    db=db,
                    payment_id=payment.id,
                    event="PAYMENT_FAILED",
                    description=(
                        "Payment verified as FAILED by "
                        "the payment provider."
                    )
                )

        # =====================================================
        # REFUNDED
        # =====================================================

        elif provider_status == "REFUNDED":

            existing_refunded_audit = (
                db.query(PaymentAudit)
                .filter(
                    PaymentAudit.payment_id == payment.id,
                    PaymentAudit.event == "PAYMENT_REFUNDED"
                )
                .first()
            )

            if existing_refunded_audit is None:
                PaymentAuditService.log(
                    db=db,
                    payment_id=payment.id,
                    event="PAYMENT_REFUNDED",
                    description=(
                        "Payment verified as REFUNDED by "
                        "the payment provider."
                    )
                )

        # =====================================================
        # PENDING
        # =====================================================

        elif provider_status == "PENDING":

            existing_pending_audit = (
                db.query(PaymentAudit)
                .filter(
                    PaymentAudit.payment_id == payment.id,
                    PaymentAudit.event == "PAYMENT_PENDING"
                )
                .first()
            )

            if existing_pending_audit is None:
                PaymentAuditService.log(
                    db=db,
                    payment_id=payment.id,
                    event="PAYMENT_PENDING",
                    description=(
                        "Payment remains PENDING after "
                        "provider verification."
                    )
                )

        db.commit()
        db.refresh(payment)

        return payment

    except HTTPException:
        db.rollback()
        raise

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to verify payment"
        )