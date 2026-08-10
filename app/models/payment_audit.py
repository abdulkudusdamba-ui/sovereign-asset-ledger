from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text
)

from datetime import datetime

from app.database.database import Base


class PaymentAudit(Base):
    __tablename__ = "payment_audits"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(
        Integer,
        ForeignKey("payments.id"),
        nullable=False
    )

    event = Column(
        String,
        nullable=False
    )

    description = Column(Text)

    actor = Column(
        String,
        default="SYSTEM"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )