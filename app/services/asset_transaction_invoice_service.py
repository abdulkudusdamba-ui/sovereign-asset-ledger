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

        if commit:
            db.commit()
            db.refresh(invoice)
        else:
            db.flush()

        return invoice
