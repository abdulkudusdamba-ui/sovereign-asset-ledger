from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.payment_reconciliation import PaymentReconciliation
from app.models.ledger_entry import LedgerEntry
from app.models.payment_audit import PaymentAudit
from app.models.asset_transaction import AssetTransaction

from app.services.payment_audit_service import PaymentAuditService
from app.services.asset_transaction_service import AssetTransactionService


class SettlementService:

    @staticmethod
    def get_settlement_status(
        db: Session,
        payment_id: int
    ) -> dict:
        """
        Determine whether a payment has reached financial
        settlement.

        Settlement requires:

        1. Payment = PAID
        2. Reconciliation = MATCHED
        3. Ledger contains PAYMENT_RECEIVED
        """

        payment = (
            db.query(Payment)
            .filter(Payment.id == payment_id)
            .first()
        )

        if not payment:
            raise ValueError("Payment not found")

        if payment.status != "PAID":
            return {
                "payment_id": payment.id,
                "status": "NOT_PAID",
                "settled": False,
                "reason": (
                    "Payment has not been verified as PAID."
                )
            }

        reconciliation = (
            db.query(PaymentReconciliation)
            .filter(
                PaymentReconciliation.payment_id
                == payment.id
            )
            .first()
        )

        if not reconciliation:
            return {
                "payment_id": payment.id,
                "status": "NOT_RECONCILED",
                "settled": False,
                "reason": (
                    "Payment has no reconciliation record."
                )
            }

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

        ledger_entry = (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.payment_id == payment.id,
                LedgerEntry.entry_type
                == "PAYMENT_RECEIVED"
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
        payment_id: int,
        commit: bool = True
    ) -> dict:
        """
        Complete financial settlement and, where applicable,
        complete the linked asset transaction.

        commit=True:
            Settlement owns the transaction.

        commit=False:
            Caller owns the transaction.

        The complete payment verification workflow should use
        commit=False and perform ONE final commit at the outer
        workflow boundary.
        """

        try:
            # -------------------------------------------------
            # 1. Verify financial settlement
            # -------------------------------------------------

            result = SettlementService.get_settlement_status(
                db=db,
                payment_id=payment_id
            )

            if not result["settled"]:
                return result

            payment = (
                db.query(Payment)
                .filter(Payment.id == payment_id)
                .first()
            )

            if not payment:
                raise ValueError("Payment not found")

            # -------------------------------------------------
            # 2. Financial settlement audit
            # -------------------------------------------------

            existing_audit = (
                db.query(PaymentAudit)
                .filter(
                    PaymentAudit.payment_id
                    == payment_id,
                    PaymentAudit.event
                    == "PAYMENT_SETTLED"
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
                        "Payment is PAID, reconciliation is "
                        "MATCHED, and ledger entry is posted."
                    )
                )

            # -------------------------------------------------
            # 3. Find invoice
            # -------------------------------------------------

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

            # -------------------------------------------------
            # 4. Process linked asset transaction
            # -------------------------------------------------

            prefix = "ASSET_TRANSACTION:"

            if (
                invoice.service
                and invoice.service.startswith(prefix)
            ):
                transaction_id_text = (
                    invoice.service[len(prefix):]
                )

                try:
                    asset_transaction_id = int(
                        transaction_id_text
                    )
                except ValueError:
                    raise ValueError(
                        "Invalid asset transaction reference "
                        "in invoice service"
                    )

                asset_transaction = (
                    db.query(AssetTransaction)
                    .filter(
                        AssetTransaction.id
                        == asset_transaction_id
                    )
                    .first()
                )

                if not asset_transaction:
                    raise ValueError(
                        "Linked asset transaction not found"
                    )

                # -------------------------------------------------
                # 5. Verify the transaction amount/currency
                # -------------------------------------------------

                if abs(
                    float(asset_transaction.amount)
                    - float(payment.amount)
                ) > 0.01:
                    raise ValueError(
                        "Asset transaction amount does not "
                        "match payment amount"
                    )

                if (
                    asset_transaction.currency.upper()
                    != payment.currency.upper()
                ):
                    raise ValueError(
                        "Asset transaction currency does not "
                        "match payment currency"
                    )

                # -------------------------------------------------
                # 6. Attach payment safely
                # -------------------------------------------------

                if asset_transaction.payment_id is None:

                    AssetTransactionService.attach_payment(
                        db=db,
                        transaction_id=asset_transaction.id,
                        payment_id=payment.id,
                        commit=False
                    )

                elif (
                    asset_transaction.payment_id
                    != payment.id
                ):
                    raise ValueError(
                        "Asset transaction is already linked "
                        "to another payment."
                    )

                # -------------------------------------------------
                # 7. Complete asset transaction
                #
                # Only financial settlement can reach this point.
                # -------------------------------------------------

                if asset_transaction.status != "COMPLETED":
                    asset_transaction.status = "COMPLETED"

                # -------------------------------------------------
                # 8. Completion audit
                # -------------------------------------------------

                completion_audit = (
                    db.query(PaymentAudit)
                    .filter(
                        PaymentAudit.payment_id
                        == payment.id,
                        PaymentAudit.event
                        == "ASSET_TRANSACTION_COMPLETED"
                    )
                    .first()
                )

                if not completion_audit:
                    PaymentAuditService.log(
                        db=db,
                        payment_id=payment.id,
                        event="ASSET_TRANSACTION_COMPLETED",
                        description=(
                            f"Asset transaction "
                            f"{asset_transaction.id} "
                            f"completed after financial settlement."
                        )
                    )

            # -------------------------------------------------
            # 9. Commit only if this service owns transaction
            # -------------------------------------------------

            if commit:
                db.commit()

            # -------------------------------------------------
            # 10. Read final state
            # -------------------------------------------------

            reconciliation = (
                db.query(PaymentReconciliation)
                .filter(
                    PaymentReconciliation.payment_id
                    == payment.id
                )
                .first()
            )

            ledger_entry = (
                db.query(LedgerEntry)
                .filter(
                    LedgerEntry.payment_id == payment.id,
                    LedgerEntry.entry_type
                    == "PAYMENT_RECEIVED"
                )
                .first()
            )

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
                "ledger_entry_id": (
                    ledger_entry.id
                    if ledger_entry
                    else None
                ),
                "reconciliation_id": (
                    reconciliation.id
                    if reconciliation
                    else None
                )
            }

        except Exception:
            if commit:
                db.rollback()
            raise
