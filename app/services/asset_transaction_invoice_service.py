from sqlalchemy.orm import Session

from app.models.asset_transaction import AssetTransaction
from app.models.invoice import Invoice

from app.services.invoice_service import InvoiceService


class AssetTransactionInvoiceService:

    @staticmethod
    def create_invoice(
        db: Session,
        transaction_id: int
    ) -> Invoice:

        # -------------------------------------------------
        # 1. Find asset transaction
        # -------------------------------------------------

        transaction = (
            db.query(AssetTransaction)
            .filter(
                AssetTransaction.id == transaction_id
            )
            .first()
        )

        if not transaction:
            raise ValueError(
                "Asset transaction not found"
            )

        # -------------------------------------------------
        # 2. Transaction must not already have a payment
        # -------------------------------------------------
        # A payment means the transaction is already inside
        # the financial workflow. Do not create another
        # invoice accidentally.
        # -------------------------------------------------

        if transaction.payment_id is not None:

            raise ValueError(
                "Asset transaction already has a payment"
            )

        # -------------------------------------------------
        # 3. Check whether an invoice already exists
        # -------------------------------------------------
        # The current Invoice model does not have an
        # asset_transaction_id column, so we cannot create
        # a direct database relationship yet.
        #
        # For now, use the transaction ID in the service
        # description as the controlled reference.
        # -------------------------------------------------

        existing_invoice = (
            db.query(Invoice)
            .filter(
                Invoice.service ==
                f"ASSET_TRANSACTION:{transaction.id}"
            )
            .first()
        )

        if existing_invoice:

            return existing_invoice

        # -------------------------------------------------
        # 4. Calculate invoice amount
        # -------------------------------------------------

        subtotal = float(transaction.amount)

        tax = 0.0
        discount = 0.0

        total = InvoiceService.calculate_total(
            subtotal=subtotal,
            tax=tax,
            discount=discount
        )

        # -------------------------------------------------
        # 5. Determine customer
        # -------------------------------------------------

        customer = (
            transaction.buyer
            or transaction.seller
            or "SAL Customer"
        )

        # -------------------------------------------------
        # 6. Create invoice
        # -------------------------------------------------

        invoice = Invoice(
            invoice_number=(
                InvoiceService.generate_invoice_number(db)
            ),
            customer=customer,
            service=(
                f"ASSET_TRANSACTION:{transaction.id}"
            ),
            currency=transaction.currency,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total=total,
            status="PENDING"
        )

        db.add(invoice)

        db.commit()
        db.refresh(invoice)

        return invoice
