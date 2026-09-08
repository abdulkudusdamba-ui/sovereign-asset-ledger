from sqlalchemy.orm import Session

from app.models.payment import Payment


class PaymentStateService:

    ALLOWED_STATUSES = {
        "PENDING",
        "PAID",
        "FAILED",
        "REFUNDED",
    }

    ALLOWED_TRANSITIONS = {
        "PENDING": {"PENDING", "PAID", "FAILED"},
        "PAID": {"PAID", "REFUNDED"},
        "FAILED": {"FAILED"},
        "REFUNDED": {"REFUNDED"},
    }

    @staticmethod
    def normalize_status(status: str) -> str:
        if not status:
            raise ValueError("Payment status is required")

        normalized = str(status).strip().upper()

        if normalized not in PaymentStateService.ALLOWED_STATUSES:
            raise ValueError(
                f"Unsupported payment status: {normalized}"
            )

        return normalized

    @staticmethod
    def validate_transition(
        current_status: str,
        new_status: str
    ) -> str:

        current = PaymentStateService.normalize_status(
            current_status
        )

        new = PaymentStateService.normalize_status(
            new_status
        )

        allowed = PaymentStateService.ALLOWED_TRANSITIONS.get(
            current,
            set()
        )

        if new not in allowed:
            raise ValueError(
                f"Invalid payment state transition: "
                f"{current} -> {new}"
            )

        return new

    @staticmethod
    def transition(
        db: Session,
        payment_id: int,
        new_status: str,
        commit: bool = True
    ) -> Payment:

        payment = (
            db.query(Payment)
            .filter(Payment.id == payment_id)
            .first()
        )

        if not payment:
            raise ValueError("Payment not found")

        normalized_status = PaymentStateService.validate_transition(
            current_status=payment.status,
            new_status=new_status
        )

        payment.status = normalized_status

        if commit:
            db.commit()
            db.refresh(payment)
        else:
            db.flush()

        return payment
