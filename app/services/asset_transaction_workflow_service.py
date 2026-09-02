from sqlalchemy.orm import Session

from app.services.asset_transaction_service import AssetTransactionService
from app.services.asset_transaction_invoice_service import (
    AssetTransactionInvoiceService
)
from app.services.payment_service import PaymentService


class AssetTransactionWorkflowService:

    @staticmethod
    def create_workflow(
        db: Session,
        asset_id: int | None,
        asset_type: str,
        transaction_type: str,
        seller: str | None,
        buyer: str | None,
        amount: float,
        currency: str = "GHS",
        description: str | None = None,
        provider: str = "sandbox",
        payment_method: str = "MOBILE_MONEY"
    ) -> dict:

        try:
            # ---------------------------------------------
            # 1. Create asset transaction
            # ---------------------------------------------

            transaction = AssetTransactionService.create_transaction(
                db=db,
                asset_id=asset_id,
                asset_type=asset_type,
                transaction_type=transaction_type,
                seller=seller,
                buyer=buyer,
                amount=amount,
                currency=currency,
                description=description,
                commit=False
            )

            # ---------------------------------------------
            # 2. Create invoice
            # ---------------------------------------------

            invoice = AssetTransactionInvoiceService.create_invoice(
                db=db,
                transaction_id=transaction.id,
                commit=False
            )

            # ---------------------------------------------
            # 3. Create payment
            # ---------------------------------------------

            payment = PaymentService.create_payment(
                db=db,
                invoice_id=invoice.id,
                provider=provider,
                payment_method=payment_method,
                commit=False
            )

            # ---------------------------------------------
            # 4. Attach payment
            # ---------------------------------------------

            transaction = AssetTransactionService.attach_payment(
                db=db,
                transaction_id=transaction.id,
                payment_id=payment.id,
                commit=False
            )

            # ---------------------------------------------
            # 5. Commit EVERYTHING together
            # ---------------------------------------------

            db.commit()

            # Refresh after the single successful commit.
            db.refresh(transaction)
            db.refresh(invoice)
            db.refresh(payment)

            return {
                "transaction": transaction,
                "invoice": invoice,
                "payment": payment
            }

        except Exception:
            # ---------------------------------------------
            # ANY FAILURE = ROLLBACK EVERYTHING
            # ---------------------------------------------

            db.rollback()
            raise
