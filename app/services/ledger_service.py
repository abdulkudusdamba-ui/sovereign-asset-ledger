from datetime import datetime

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.ledger_entry import LedgerEntry


class LedgerService:

    @staticmethod
    def record_payment(
        db: Session,
        payment_id: int
    ):

        payment = (
            db.query(Payment)
            .filter(Payment.id == payment_id)
            .first()
        )

        if not payment:
            raise ValueError("Payment not found")

        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == payment.invoice_id)
            .first()
        )

        if not invoice:
            raise ValueError("Invoice not found")

        # Prevent duplicate ledger entries
        existing = (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.payment_id == payment.id,
                LedgerEntry.entry_type == "PAYMENT_RECEIVED"
            )
            .first()
        )

        if existing:
            return existing

        entry = LedgerEntry(
            payment_id=payment.id,
            invoice_id=invoice.id,
            transaction_id=payment.transaction_id,
            entry_type="PAYMENT_RECEIVED",
            direction="CREDIT",
            amount=payment.amount,
            currency=payment.currency,
            description=(
                f"Payment received for invoice "
                f"{invoice.invoice_number}."
            ),
            reference=payment.provider_reference,
            created_at=datetime.utcnow()
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)

        return entry
