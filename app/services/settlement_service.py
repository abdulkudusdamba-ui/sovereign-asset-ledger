from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_reconciliation import PaymentReconciliation
from app.models.ledger_entry import LedgerEntry
from app.models.payment_audit import PaymentAudit
from app.services.payment_audit_service import PaymentAuditService


class SettlementService:

    @staticmethod
    def get_settlement_status(
        db: Session,
        payment_id: int
    ) -> dict:

        payment = (
            db.query(Payment)
            .filter(Payment.id == payment_id)
            .first()
        )

        if not payment:
            raise ValueError("Payment not found")

        # -------------------------------------------------
        # 1. Payment must be PAID
        # -------------------------------------------------

        if payment.status != "PAID":
            return {
                "payment_id": payment.id,
                "status": "NOT_PAID",
                "settled": False,
                "reason": "Payment has not been marked as PAID."
            }

        # -------------------------------------------------
        # 2. Payment must have reconciliation
        # -------------------------------------------------

        reconciliation = (
            db.query(PaymentReconciliation)
            .filter(
                PaymentReconciliation.payment_id == payment.id
            )
            .first()
        )

        if not reconciliation:
            return {
                "payment_id": payment.id,
                "status": "NOT_RECONCILED",
                "settled": False,
                "reason": "Payment has no reconciliation record."
            }

        # -------------------------------------------------
        # 3. Reconciliation must be MATCHED
        # -------------------------------------------------

        if reconciliation.status != "MATCHED":
            return {
                "payment_id": payment.id,
                "status": "RECONCILIATION_EXCEPTION",
                "settled": False,
                "reason": (
                    f"Payment reconciliation status is "
                    f"{reconciliation.status}."
                )
            }

        # -------------------------------------------------
        # 4. Payment must have ledger entry
        # -------------------------------------------------

        ledger_entry = (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.payment_id == payment.id,
                LedgerEntry.entry_type == "PAYMENT_RECEIVED"
            )
            .first()
        )

        if not ledger_entry:
            return {
                "payment_id": payment.id,
                "status": "LEDGER_NOT_POSTED",
                "settled": False,
                "reason": (
                    "Payment has no PAYMENT_RECEIVED "
                    "ledger entry."
                )
            }

        # -------------------------------------------------
        # 5. Financial settlement confirmed
        # -------------------------------------------------

        return {
            "payment_id": payment.id,
            "status": "FINANCIALLY_SETTLED",
            "settled": True,
            "reason": (
                "Payment is PAID, reconciliation is MATCHED, "
                "and the payment is posted to the financial ledger."
            ),
            "transaction_id": payment.transaction_id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "ledger_entry_id": ledger_entry.id,
            "reconciliation_id": reconciliation.id
        }

    @staticmethod
    def settle_payment(
        db: Session,
        payment_id: int
    ) -> dict:

        result = SettlementService.get_settlement_status(
            db=db,
            payment_id=payment_id
        )

        if not result["settled"]:
            return result

        # -------------------------------------------------
        # Prevent duplicate settlement audits
        # -------------------------------------------------

        existing_audit = (
            db.query(PaymentAudit)
            .filter(
                PaymentAudit.payment_id == payment_id,
                PaymentAudit.event == "PAYMENT_SETTLED"
            )
            .first()
        )

        if not existing_audit:

            PaymentAuditService.log(
                db=db,
                payment_id=payment_id,
                event="PAYMENT_SETTLED",
                description=(
                    "Payment financially settled. "
                    "Payment is PAID, reconciliation is MATCHED, "
                    "and ledger entry is posted."
                )
            )

            db.commit()

        return result