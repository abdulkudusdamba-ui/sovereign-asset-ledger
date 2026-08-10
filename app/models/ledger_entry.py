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


class LedgerEntry(Base):

    __tablename__ = "ledger_entries"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    payment_id = Column(
        Integer,
        ForeignKey("payments.id"),
        nullable=True,
        index=True
    )

    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id"),
        nullable=True,
        index=True
    )

    transaction_id = Column(
        String,
        nullable=True,
        index=True
    )

    entry_type = Column(
        String,
        nullable=False
    )

    direction = Column(
        String,
        nullable=False
    )

    amount = Column(
        Float,
        nullable=False
    )

    currency = Column(
        String,
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    reference = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
