from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.sql import func

from app.database.database import Base


class AuditEvent(Base):
    """
    Immutable system-generated Audit Trail event.

    Audit events record who did what, to which SAL entity,
    when it occurred, when SAL received it, where it came from,
    and the relevant before/after state.

    Audit events are not legal ownership records.
    They provide an operational, security, compliance,
    and dispute-resolution history for SAL.
    """

    __tablename__ = "audit_events"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_id = Column(
        String,
        unique=True,
        nullable=False,
    )

    actor_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    actor_type = Column(
        String,
        nullable=False,
    )

    action = Column(
        String,
        nullable=False,
        index=True,
    )

    entity_type = Column(
        String,
        nullable=False,
    )

    entity_id = Column(
        String,
        nullable=False,
    )

    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        nullable=True,
        index=True,
    )

    passport_id = Column(
        Integer,
        ForeignKey("asset_passports.id"),
        nullable=True,
        index=True,
    )

    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    received_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    source = Column(
        String,
        nullable=False,
    )

    device_id = Column(
        String,
        nullable=True,
    )

    ip_address = Column(
        String,
        nullable=True,
    )

    user_agent = Column(
        String,
        nullable=True,
    )

    reason = Column(
        String,
        nullable=True,
    )

    reference = Column(
        String,
        nullable=True,
        index=True,
    )

    result = Column(
        String,
        nullable=False,
    )

    before_data = Column(
        String,
        nullable=True,
    )

    after_data = Column(
        String,
        nullable=True,
    )

    audit_metadata = Column(
        "metadata",
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_audit_events_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_audit_events_occurred_at",
            "occurred_at",
        ),
    )
