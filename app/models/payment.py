from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey
)

from datetime import datetime

from app.database.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id"),
        nullable=False
    )

    transaction_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    provider = Column(
        String,
        nullable=False
    )

    payment_method = Column(
        String,
        nullable=False
    )

    currency = Column(
        String,
        default="GHS"
    )

    amount = Column(
        Float,
        nullable=False
    )

    status = Column(
        String,
        default="PENDING"
    )

    provider_reference = Column(String)

    paid_at = Column(DateTime)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
