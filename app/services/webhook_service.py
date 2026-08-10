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


class WebhookService:

    @staticmethod
    def generate_event_key(
        provider: str,
        event_type: str,
        transaction_id: str | None,
    ) -> str:

        raw = (
            f"{provider}:"
            f"{event_type}:"
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

        # =====================================================
        # 1. Generate deterministic event key
        # =====================================================

        event_key = WebhookService.generate_event_key(
            provider=provider,
            event_type=event_type,
            transaction_id=transaction_id,
        )

        # =====================================================
        # 2. Check for already processed webhook
        # =====================================================

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
                provider=provider,
                event_type=event_type,
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
            db.commit()
            db.refresh(webhook)

        # =====================================================
        # 3. Find payment
        # =====================================================

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

            db.commit()
            db.refresh(webhook)

            return webhook

        # =====================================================
        # 4. Update payment status
        # =====================================================

        if status:
            payment.status = status

        # =====================================================
        # 5. Handle PAID
        # =====================================================

        if status == "PAID":

            if payment.paid_at is None:
                payment.paid_at = datetime.utcnow()

            invoice = (
                db.query(Invoice)
                .filter(
                    Invoice.id == payment.invoice_id
                )
                .first()
            )

            if invoice:

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
                        f"{provider} webhook."
                    ),
                )

        # =====================================================
        # 6. Handle FAILED
        # =====================================================

        elif status == "FAILED":

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
                        f"{provider} webhook."
                    ),
                )

        # =====================================================
        # 7. Handle REFUNDED
        # =====================================================

        elif status == "REFUNDED":

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
                        f"{provider} webhook."
                    ),
                )

        # =====================================================
        # 8. Mark webhook processed
        # =====================================================

        webhook.status = "PROCESSED"
        webhook.processed_at = datetime.utcnow()

        db.commit()
        db.refresh(webhook)

        return webhook