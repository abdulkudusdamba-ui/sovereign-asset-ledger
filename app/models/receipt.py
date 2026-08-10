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


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(
        Integer,
        ForeignKey("payments.id"),
        nullable=False
    )

    receipt_number = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    customer = Column(String, nullable=False)

    currency = Column(String, default="GHS")

    amount = Column(Float, nullable=False)

    issued_at = Column(
        DateTime,
        default=datetime.utcnow
    )
