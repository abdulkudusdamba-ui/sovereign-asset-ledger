from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.payment_reconciliation import PaymentReconciliation
from app.models.ledger_entry import LedgerEntry


class ReportingService:

    @staticmethod
    def get_financial_summary(db: Session):

        total_payments = (
            db.query(func.count(Payment.id))
            .scalar()
            or 0
        )

        total_payment_amount = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.status == "PAID")
            .scalar()
            or 0
        )

        total_invoices = (
            db.query(func.count(Invoice.id))
            .scalar()
            or 0
        )

        paid_invoices = (
            db.query(func.count(Invoice.id))
            .filter(Invoice.status == "PAID")
            .scalar()
            or 0
        )

        outstanding_invoices = (
            db.query(func.count(Invoice.id))
            .filter(Invoice.status != "PAID")
            .scalar()
            or 0
        )

        matched_reconciliations = (
            db.query(func.count(PaymentReconciliation.id))
            .filter(
                PaymentReconciliation.status == "MATCHED"
            )
            .scalar()
            or 0
        )

        underpaid_reconciliations = (
            db.query(func.count(PaymentReconciliation.id))
            .filter(
                PaymentReconciliation.status == "UNDERPAID"
            )
            .scalar()
            or 0
        )

        overpaid_reconciliations = (
            db.query(func.count(PaymentReconciliation.id))
            .filter(
                PaymentReconciliation.status == "OVERPAID"
            )
            .scalar()
            or 0
        )

        ledger_entries = (
            db.query(func.count(LedgerEntry.id))
            .scalar()
            or 0
        )

        ledger_credits = (
            db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .filter(
                LedgerEntry.direction == "CREDIT"
            )
            .scalar()
            or 0
        )

        return {
            "total_payments": total_payments,
            "total_payment_amount": float(total_payment_amount),
            "total_invoices": total_invoices,
            "paid_invoices": paid_invoices,
            "outstanding_invoices": outstanding_invoices,
            "matched_reconciliations": matched_reconciliations,
            "underpaid_reconciliations": underpaid_reconciliations,
            "overpaid_reconciliations": overpaid_reconciliations,
            "ledger_entries": ledger_entries,
            "ledger_credits": float(ledger_credits),
        }

    @staticmethod
    def get_payment_summary(db: Session):

        paid = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "PAID")
            .scalar()
            or 0
        )

        pending = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "PENDING")
            .scalar()
            or 0
        )

        failed = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "FAILED")
            .scalar()
            or 0
        )

        refunded = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "REFUNDED")
            .scalar()
            or 0
        )

        return {
            "paid": paid,
            "pending": pending,
            "failed": failed,
            "refunded": refunded,
        }
