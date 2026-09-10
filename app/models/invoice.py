from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
)
from datetime import datetime

from app.database.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    invoice_number = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    customer = Column(
        String,
        nullable=False
    )

    service = Column(
        String,
        nullable=False
    )

    # Application-level relationship to an asset transaction.
    #
    # The SQLite prototype already contains this column.
    # We intentionally do not add a physical SQLite FK here because
    # the current database was recovered after a failed SQLite rebuild.
    asset_transaction_id = Column(
        Integer,
        nullable=True,
        index=True
    )

    currency = Column(
        String,
        default="GHS"
    )

    subtotal = Column(
        Float,
        default=0
    )

    tax = Column(
        Float,
        default=0
    )

    discount = Column(
        Float,
        default=0
    )

    total = Column(
        Float,
        default=0
    )

    status = Column(
        String,
        default="DRAFT"
    )

    due_date = Column(
        DateTime
    )

    paid_at = Column(
        DateTime
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
