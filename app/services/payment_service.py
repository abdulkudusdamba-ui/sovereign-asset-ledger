from datetime import datetime

from sqlalchemy.orm import Session

from app.models.payment import Payment


class PaymentService:

    @staticmethod
    def generate_transaction_id():
        year = datetime.utcnow().year
        timestamp = int(datetime.utcnow().timestamp())
        return f"SAL-PAY-{year}-{timestamp}"

    @staticmethod
    def create_payment(
        db: Session,
        invoice_id: int,
        provider="sandbox",
        payment_method="MOBILE_MONEY",
        commit: bool = True
    ) -> Payment:

        from app.models.invoice import Invoice

        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == invoice_id)
            .first()
        )

        if not invoice:
            raise ValueError("Invoice not found")

        existing_payment = (
            db.query(Payment)
            .filter(
                Payment.invoice_id == invoice.id
            )
            .first()
        )

        if existing_payment:
            return existing_payment

        payment = Payment(
            invoice_id=invoice.id,
            transaction_id=(
                PaymentService.generate_transaction_id()
            ),
            provider=provider,
            payment_method=payment_method,
            currency=invoice.currency,
            amount=invoice.total,
            status="PENDING"
        )

        db.add(payment)

        if commit:
            db.commit()
            db.refresh(payment)
        else:
            db.flush()

        return payment
