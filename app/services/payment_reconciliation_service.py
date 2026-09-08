from datetime import datetime
from decimal import Decimal

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
        """
        Determine whether the payment matches the invoice.

        MATCHED:
            Payment equals invoice total.

        UNDERPAID:
            Payment is less than invoice total.

        OVERPAID:
            Payment is greater than invoice total.
        """

        expected = Decimal(str(expected_amount))
        actual = Decimal(str(actual_amount))

        if actual == expected:
            return "MATCHED"

        if actual < expected:
            return "UNDERPAID"

        return "OVERPAID"

    @staticmethod
    def reconcile_payment(
        db: Session,
        payment_id: int,
        commit: bool = True
    ):
        """
        Reconcile a payment against its invoice.

        Transaction ownership:
            commit=True
                This method commits its own transaction.

            commit=False
                All database changes remain inside the caller's
                transaction.

        The second mode is required when reconciliation is part
        of the larger payment settlement workflow.
        """

        try:
            # -------------------------------------------------
            # 1. Find payment
            # -------------------------------------------------

            payment = (
                db.query(Payment)
                .filter(Payment.id == payment_id)
                .first()
            )

            if not payment:
                raise ValueError("Payment not found")

            # -------------------------------------------------
            # 2. Find invoice
            # -------------------------------------------------

            invoice = (
                db.query(Invoice)
                .filter(Invoice.id == payment.invoice_id)
                .first()
            )

            if not invoice:
                raise ValueError("Invoice not found")

            # -------------------------------------------------
            # 3. Prevent duplicate reconciliation
            # -------------------------------------------------

            existing = (
                db.query(PaymentReconciliation)
                .filter(
                    PaymentReconciliation.payment_id
                    == payment.id
                )
                .first()
            )

            if existing:
                return existing

            # -------------------------------------------------
            # 4. Validate amounts
            # -------------------------------------------------

            expected_amount = Decimal(
                str(invoice.total)
            )

            actual_amount = Decimal(
                str(payment.amount)
            )

            if expected_amount < Decimal("0"):
                raise ValueError(
                    "Invoice amount cannot be negative"
                )

            if actual_amount < Decimal("0"):
                raise ValueError(
                    "Payment amount cannot be negative"
                )

            # -------------------------------------------------
            # 5. Validate currencies
            # -------------------------------------------------

            if not invoice.currency:
                raise ValueError(
                    "Invoice currency is missing"
                )

            if not payment.currency:
                raise ValueError(
                    "Payment currency is missing"
                )

            invoice_currency = invoice.currency.upper()
            payment_currency = payment.currency.upper()

            if invoice_currency != payment_currency:
                raise ValueError(
                    "Payment currency does not match invoice currency"
                )

            # -------------------------------------------------
            # 6. Calculate difference
            # -------------------------------------------------

            difference = (
                actual_amount - expected_amount
            )

            status = (
                PaymentReconciliationService.determine_status(
                    float(expected_amount),
                    float(actual_amount)
                )
            )

            # -------------------------------------------------
            # 7. Create reconciliation
            # -------------------------------------------------

            reconciliation = PaymentReconciliation(
                payment_id=payment.id,
                invoice_id=invoice.id,
                expected_amount=float(expected_amount),
                actual_amount=float(actual_amount),
                currency=payment_currency,
                difference=float(difference),
                status=status,
                provider_reference=payment.provider_reference,
                notes=None,
                created_at=datetime.utcnow(),
                reconciled_at=datetime.utcnow()
            )

            db.add(reconciliation)

            # Make the reconciliation available to the rest
            # of the current transaction.
            db.flush()

            # -------------------------------------------------
            # 8. Ledger
            #
            # IMPORTANT:
            # Never commit here when this method is being used
            # as part of the complete settlement workflow.
            # -------------------------------------------------

            LedgerService.record_payment(
                db=db,
                payment_id=payment.id,
                commit=False
            )

            # -------------------------------------------------
            # 9. Audit
            # -------------------------------------------------

            PaymentAuditService.log(
                db=db,
                payment_id=payment.id,
                event="PAYMENT_RECONCILED",
                description=(
                    f"Payment reconciled as {status}. "
                    f"Expected {expected_amount:.2f} "
                    f"{invoice_currency}, received "
                    f"{actual_amount:.2f} "
                    f"{payment_currency}, difference "
                    f"{difference:.2f}."
                )
            )

            # -------------------------------------------------
            # 10. Optional transaction ownership
            # -------------------------------------------------

            if commit:
                db.commit()
                db.refresh(reconciliation)

            return reconciliation

        except Exception:
            if commit:
                db.rollback()
            raise
