from datetime import datetime

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.payment_reconciliation import PaymentReconciliation
from app.services.payment_audit_service import PaymentAuditService
from app.services.ledger_service import LedgerService


class PaymentReconciliationService:

    @staticmethod
    def determine_status(
        expected_amount: float,
        actual_amount: float
    ) -> str:

        if actual_amount == expected_amount:
            return "MATCHED"

        if actual_amount < expected_amount:
            return "UNDERPAID"

        return "OVERPAID"

    @staticmethod
    def reconcile_payment(
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

        # -------------------------------------------------
        # Prevent duplicate reconciliation
        # -------------------------------------------------

        existing = (
            db.query(PaymentReconciliation)
            .filter(
                PaymentReconciliation.payment_id == payment.id
            )
            .first()
        )

        if existing:
            return existing

        expected_amount = float(invoice.total)
        actual_amount = float(payment.amount)

        difference = actual_amount - expected_amount

        status = (
            PaymentReconciliationService.determine_status(
                expected_amount,
                actual_amount
            )
        )

        reconciliation = PaymentReconciliation(
            payment_id=payment.id,
            invoice_id=invoice.id,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            currency=payment.currency,
            difference=difference,
            status=status,
            provider_reference=payment.provider_reference,
            notes=None,
            created_at=datetime.utcnow(),
            reconciled_at=datetime.utcnow()
        )

        db.add(reconciliation)
        db.flush()

        # -------------------------------------------------
        # Create financial ledger entry
        # LedgerService has its own duplicate protection.
        # -------------------------------------------------

        LedgerService.record_payment(
            db=db,
            payment_id=payment.id
        )

        # -------------------------------------------------
        # Record reconciliation audit
        # -------------------------------------------------

        PaymentAuditService.log(
            db=db,
            payment_id=payment.id,
            event="PAYMENT_RECONCILED",
            description=(
                f"Payment reconciled as {status}. "
                f"Expected {expected_amount:.2f} "
                f"{invoice.currency}, received "
                f"{actual_amount:.2f} "
                f"{payment.currency}, difference "
                f"{difference:.2f}."
            )
        )

        db.commit()
        db.refresh(reconciliation)

        return reconciliation