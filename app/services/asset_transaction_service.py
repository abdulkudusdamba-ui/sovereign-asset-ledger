from sqlalchemy.orm import Session

from app.models.asset_transaction import AssetTransaction
from app.models.payment import Payment


class AssetTransactionService:

    @staticmethod
    def create_transaction(
        db: Session,
        asset_id: int | None,
        asset_type: str,
        transaction_type: str,
        seller: str | None,
        buyer: str | None,
        amount: float,
        currency: str = "GHS",
        description: str | None = None
    ) -> AssetTransaction:

        transaction = AssetTransaction(
            asset_id=asset_id,
            asset_type=asset_type,
            transaction_type=transaction_type,
            seller=seller,
            buyer=buyer,
            amount=amount,
            currency=currency,
            status="PENDING",
            description=description
        )

        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    @staticmethod
    def get_transaction(
        db: Session,
        transaction_id: int
    ) -> AssetTransaction | None:

        return (
            db.query(AssetTransaction)
            .filter(
                AssetTransaction.id == transaction_id
            )
            .first()
        )

    @staticmethod
    def list_transactions(
        db: Session
    ) -> list[AssetTransaction]:

        return (
            db.query(AssetTransaction)
            .order_by(
                AssetTransaction.id.desc()
            )
            .all()
        )

    @staticmethod
    def update_status(
        db: Session,
        transaction_id: int,
        status: str
    ) -> AssetTransaction | None:

        transaction = (
            db.query(AssetTransaction)
            .filter(
                AssetTransaction.id == transaction_id
            )
            .first()
        )

        if not transaction:
            return None

        transaction.status = status

        db.commit()
        db.refresh(transaction)

        return transaction

    @staticmethod
    def attach_payment(
        db: Session,
        transaction_id: int,
        payment_id: int
    ) -> AssetTransaction | None:

        transaction = (
            db.query(AssetTransaction)
            .filter(
                AssetTransaction.id == transaction_id
            )
            .first()
        )

        if not transaction:
            return None

        payment = (
            db.query(Payment)
            .filter(
                Payment.id == payment_id
            )
            .first()
        )

        if not payment:
            raise ValueError("Payment not found")

        # Prevent attaching a different payment
        # to an already-linked asset transaction.
        if transaction.payment_id is not None:
            if transaction.payment_id != payment.id:
                raise ValueError(
                    "Asset transaction is already linked "
                    "to another payment"
                )

            return transaction

        # Make sure the financial amounts agree.
        if abs(transaction.amount - payment.amount) > 0.01:
            raise ValueError(
                "Payment amount does not match "
                "asset transaction amount"
            )

        # Make sure currencies agree.
        if transaction.currency != payment.currency:
            raise ValueError(
                "Payment currency does not match "
                "asset transaction currency"
            )

        transaction.payment_id = payment.id

        db.commit()
        db.refresh(transaction)

        return transaction