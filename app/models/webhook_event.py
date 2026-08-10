from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    UniqueConstraint
)
from datetime import datetime

from app.database.database import Base


class WebhookEvent(Base):

    __tablename__ = "webhook_events"

    __table_args__ = (
        UniqueConstraint(
            "event_key",
            name="uq_webhook_event_key"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    provider = Column(
        String,
        nullable=False
    )

    event_type = Column(
        String,
        nullable=False
    )

    transaction_id = Column(
        String,
        nullable=True
    )

    event_key = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    payload = Column(
        Text,
        nullable=False
    )

    status = Column(
        String,
        default="RECEIVED"
    )

    processed_at = Column(
        DateTime,
        default=datetime.utcnow
    )
