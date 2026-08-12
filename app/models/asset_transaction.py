from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text
)
from datetime import datetime

from app.database.database import Base
from app.models.asset import Asset


class AssetTransaction(Base):
    __tablename__ = "asset_transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    asset_id = Column(
        Integer,
        ForeignKey("assets.id"),
        nullable=True
    )

    asset_type = Column(
        String,
        nullable=False
    )

    transaction_type = Column(
        String,
        nullable=False
    )

    seller = Column(
        String,
        nullable=True
    )

    buyer = Column(
        String,
        nullable=True
    )

    amount = Column(
        Float,
        nullable=False,
        default=0
    )

    currency = Column(
        String,
        nullable=False,
        default="GHS"
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING"
    )

    payment_id = Column(
        Integer,
        ForeignKey("payments.id"),
        nullable=True
    )

    description = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
