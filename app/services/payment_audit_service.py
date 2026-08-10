from sqlalchemy.orm import Session

from app.models.payment_audit import PaymentAudit


class PaymentAuditService:

    @staticmethod
    def log(
        db: Session,
        payment_id: int,
        event: str,
        description: str,
        actor: str = "SYSTEM"
    ):

        audit = PaymentAudit(
            payment_id=payment_id,
            event=event,
            description=description,
            actor=actor
        )

        db.add(audit)
