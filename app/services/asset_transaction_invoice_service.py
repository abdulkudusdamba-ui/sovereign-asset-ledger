from sqlalchemy.orm import Session

from app.models.asset_transaction import AssetTransaction
from app.models.invoice import Invoice

from app.services.invoice_service import InvoiceService


class AssetTransactionInvoiceService:

    @staticmethod
    def create_invoice(
        db: Session,
        transaction_id: int,
        commit: bool = True
    ) -> Invoice:

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

        if transaction.payment_id is not None:
            raise ValueError(
                "Asset transaction already has a payment"
            )

        # ---------------------------------------------------------
        # 1. Preferred relationship:
        #    Invoice.asset_transaction_id
        # ---------------------------------------------------------
        existing_invoice = (
            db.query(Invoice)
            .filter(
                Invoice.asset_transaction_id == transaction.id
            )
            .first()
        )

        if existing_invoice:
            return existing_invoice

        # ---------------------------------------------------------
        # 2. Legacy compatibility:
        #    Older invoices used:
        #    service = "ASSET_TRANSACTION:<id>"
        #
        #    If one exists, connect it to the new column.
        # ---------------------------------------------------------
        legacy_service = (
            f"ASSET_TRANSACTION:{transaction.id}"
        )

        existing_invoice = (
            db.query(Invoice)
            .filter(
                Invoice.service == legacy_service
            )
            .first()
        )

        if existing_invoice:
            existing_invoice.asset_transaction_id = transaction.id

            if commit:
                db.commit()
                db.refresh(existing_invoice)
            else:
                db.flush()

            return existing_invoice

        # ---------------------------------------------------------
        # 3. Create a new invoice.
        # ---------------------------------------------------------
        subtotal = float(transaction.amount)

        tax = 0.0
        discount = 0.0

        total = InvoiceService.calculate_total(
            subtotal=subtotal,
            tax=tax,
            discount=discount
        )

        customer = (
            transaction.buyer
            or transaction.seller
            or "SAL Customer"
        )

        invoice = Invoice(
            invoice_number=(
                InvoiceService.generate_invoice_number(db)
            ),
            customer=customer,

            # Keep service as a readable description.
            service=legacy_service,

            # Actual application-level relationship.
            asset_transaction_id=transaction.id,

            currency=transaction.currency,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total=total,
            status="PENDING"
        )

        db.add(invoice)

        if commit:
            db.commit()
            db.refresh(invoice)
        else:
            db.flush()

        return invoice
