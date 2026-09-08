import hashlib
import json

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.receipt import Receipt
from app.models.payment_audit import PaymentAudit

from app.services.receipt_service import ReceiptService
from app.services.payment_audit_service import PaymentAuditService
from app.services.payment_state_service import PaymentStateService
from app.services.payment_reconciliation_service import (
    PaymentReconciliationService,
)
from app.services.settlement_service import SettlementService


class WebhookService:

    @staticmethod
    def generate_event_key(
        provider: str,
        event_type: str,
        transaction_id: str | None,
    ) -> str:

        raw = (
            f"{provider.strip().lower()}:"
            f"{event_type.strip().upper()}:"
            f"{transaction_id}"
        )

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def process_payment_webhook(
        db: Session,
        provider: str,
        event_type: str,
        transaction_id: str | None,
        status: str | None,
        payload: dict,
    ):

        try:
            if not provider:
                raise ValueError("Webhook provider is required")

            if not event_type:
                raise ValueError("Webhook event type is required")

            normalized_provider = provider.strip().lower()
            normalized_event_type = event_type.strip().upper()

            normalized_status = None

            if status is not None:
                normalized_status = PaymentStateService.normalize_status(
                    status
                )

            event_key = WebhookService.generate_event_key(
                provider=normalized_provider,
                event_type=normalized_event_type,
                transaction_id=transaction_id,
            )

            existing_webhook = (
                db.query(WebhookEvent)
                .filter(
                    WebhookEvent.event_key == event_key
                )
                .first()
            )

            if existing_webhook:

                if existing_webhook.status == "PROCESSED":
                    return existing_webhook

                if existing_webhook.status == "PROCESSING":
                    return existing_webhook

                webhook = existing_webhook

            else:

                webhook = WebhookEvent(
                    provider=normalized_provider,
                    event_type=normalized_event_type,
                    transaction_id=transaction_id,
                    event_key=event_key,
                    payload=json.dumps(
                        payload,
                        sort_keys=True
                    ),
                    status="PROCESSING",
                    processed_at=datetime.utcnow(),
                )

                db.add(webhook)
                db.flush()

            payment = None

            if transaction_id:

                payment = (
                    db.query(Payment)
                    .filter(
                        Payment.transaction_id == transaction_id
                    )
                    .first()
                )

            if not payment:

                webhook.status = "PAYMENT_NOT_FOUND"
                webhook.processed_at = datetime.utcnow()

                db.commit()
                db.refresh(webhook)

                return webhook

            # =================================================
            # Provider ownership verification
            # =================================================
            #
            # A webhook authenticated as one provider must
            # never be allowed to modify a payment belonging
            # to another provider.
            #
            # Example:
            #
            # webhook provider = sandbox
            # payment provider = mtn
            #
            # -> reject
            #
            if not payment.provider:
                raise ValueError(
                    "Payment provider is missing"
                )

            if (
                payment.provider.strip().lower()
                != normalized_provider
            ):
                raise ValueError(
                    "Webhook provider does not match payment provider"
                )

            if normalized_status is None:
                raise ValueError(
                    "Webhook payment status is required"
                )

            # =================================================
            # Central payment state machine
            # =================================================

            PaymentStateService.transition(
                db=db,
                payment_id=payment.id,
                new_status=normalized_status,
                commit=False
            )

            db.refresh(payment)

            # =================================================
            # PAID
            # =================================================

            if normalized_status == "PAID":

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
                        "Invoice not found for payment"
                    )

                if not invoice.currency:
                    raise ValueError(
                        "Invoice currency is missing"
                    )

                if not payment.currency:
                    raise ValueError(
                        "Payment currency is missing"
                    )

                if (
                    invoice.currency.upper()
                    != payment.currency.upper()
                ):
                    raise ValueError(
                        "Payment currency does not match invoice currency"
                    )

                if abs(
                    float(payment.amount)
                    - float(invoice.total)
                ) > 0.01:
                    raise ValueError(
                        "Payment amount does not match invoice total"
                    )

                invoice.status = "PAID"
                invoice.paid_at = payment.paid_at

                # ---------------------------------------------
                # Receipt idempotency
                # ---------------------------------------------

                existing_receipt = (
                    db.query(Receipt)
                    .filter(
                        Receipt.payment_id == payment.id
                    )
                    .first()
                )

                if existing_receipt is None:

                    receipt = Receipt(
                        payment_id=payment.id,
                        receipt_number=(
                            ReceiptService
                            .generate_receipt_number(db)
                        ),
                        customer=invoice.customer,
                        currency=invoice.currency,
                        amount=payment.amount,
                    )

                    db.add(receipt)
                    db.flush()

                    existing_receipt_audit = (
                        db.query(PaymentAudit)
                        .filter(
                            PaymentAudit.payment_id == payment.id,
                            PaymentAudit.event
                            == "RECEIPT_GENERATED",
                        )
                        .first()
                    )

                    if existing_receipt_audit is None:

                        PaymentAuditService.log(
                            db=db,
                            payment_id=payment.id,
                            event="RECEIPT_GENERATED",
                            description=(
                                f"Receipt "
                                f"{receipt.receipt_number} "
                                "generated from webhook."
                            ),
                        )

                # ---------------------------------------------
                # PAYMENT_PAID audit idempotency
                # ---------------------------------------------

                existing_paid_audit = (
                    db.query(PaymentAudit)
                    .filter(
                        PaymentAudit.payment_id == payment.id,
                        PaymentAudit.event == "PAYMENT_PAID",
                    )
                    .first()
                )

                if existing_paid_audit is None:

                    PaymentAuditService.log(
                        db=db,
                        payment_id=payment.id,
                        event="PAYMENT_PAID",
                        description=(
                            f"Payment marked PAID by "
                            f"{normalized_provider} webhook."
                        ),
                    )

                # ---------------------------------------------
                # Financial reconciliation + settlement
                # ---------------------------------------------

                db.flush()

                PaymentReconciliationService.reconcile_payment(
                    db=db,
                    payment_id=payment.id,
                    commit=False
                )

                SettlementService.settle_payment(
                    db=db,
                    payment_id=payment.id,
                    commit=False
                )

            # =================================================
            # FAILED
            # =================================================

            elif normalized_status == "FAILED":

                existing_failed_audit = (
                    db.query(PaymentAudit)
                    .filter(
                        PaymentAudit.payment_id == payment.id,
                        PaymentAudit.event == "PAYMENT_FAILED",
                    )
                    .first()
                )

                if existing_failed_audit is None:

                    PaymentAuditService.log(
                        db=db,
                        payment_id=payment.id,
                        event="PAYMENT_FAILED",
                        description=(
                            f"Payment failed according to "
                            f"{normalized_provider} webhook."
                        ),
                    )

            # =================================================
            # REFUNDED
            # =================================================

            elif normalized_status == "REFUNDED":

                existing_refund_audit = (
                    db.query(PaymentAudit)
                    .filter(
                        PaymentAudit.payment_id == payment.id,
                        PaymentAudit.event == "PAYMENT_REFUNDED",
                    )
                    .first()
                )

                if existing_refund_audit is None:

                    PaymentAuditService.log(
                        db=db,
                        payment_id=payment.id,
                        event="PAYMENT_REFUNDED",
                        description=(
                            f"Payment refunded according to "
                            f"{normalized_provider} webhook."
                        ),
                    )

            # =================================================
            # PENDING
            # =================================================

            elif normalized_status == "PENDING":

                existing_pending_audit = (
                    db.query(PaymentAudit)
                    .filter(
                        PaymentAudit.payment_id == payment.id,
                        PaymentAudit.event == "PAYMENT_PENDING",
                    )
                    .first()
                )

                if existing_pending_audit is None:

                    PaymentAuditService.log(
                        db=db,
                        payment_id=payment.id,
                        event="PAYMENT_PENDING",
                        description=(
                            f"Payment remains PENDING according "
                            f"to {normalized_provider} webhook."
                        ),
                    )

            # =================================================
            # Complete webhook
            # =================================================

            webhook.status = "PROCESSED"
            webhook.processed_at = datetime.utcnow()

            db.commit()
            db.refresh(webhook)

            return webhook

        except Exception:
            db.rollback()
            raise
