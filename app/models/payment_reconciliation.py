from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)

from datetime import datetime

from app.database.database import Base


class PaymentReconciliation(Base):

    __tablename__ = "payment_reconciliations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    payment_id = Column(
        Integer,
        ForeignKey("payments.id"),
        nullable=False,
        index=True
    )

    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id"),
        nullable=False,
        index=True
    )

    expected_amount = Column(
        Float,
        nullable=False
    )

    actual_amount = Column(
        Float,
        nullable=False
    )

    currency = Column(
        String,
        nullable=False
    )

    difference = Column(
        Float,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING"
    )

    provider_reference = Column(
        String,
        nullable=True
    )

    notes = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    reconciled_at = Column(
        DateTime,
        nullable=True
    )