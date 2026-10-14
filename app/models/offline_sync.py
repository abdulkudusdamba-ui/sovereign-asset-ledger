from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database.database import Base


class OfflineSyncOperation(Base):
    __tablename__ = "offline_sync_operations"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operation_id = Column(String(36), nullable=False)
    asset_type = Column(String(50), nullable=False)
    request_hash = Column(String(64), nullable=False)
    request_payload = Column(Text, nullable=False)
    status = Column(String(40), nullable=False)
    result_payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("actor_id", "operation_id", name="uq_offline_operation_actor_id"),
        Index("ix_offline_sync_operations_actor_created", "actor_id", "created_at"),
    )


class OfflineSyncConflict(Base):
    __tablename__ = "offline_sync_conflicts"

    id = Column(Integer, primary_key=True)
    operation_record_id = Column(
        Integer,
        ForeignKey("offline_sync_operations.id"),
        nullable=False,
    )
    submission_hash = Column(String(64), nullable=False)
    conflict_type = Column(String(50), nullable=False)
    asset_type = Column(String(50), nullable=False)
    identifier_type = Column(String(50), nullable=True)
    identifier_value = Column(String(200), nullable=True)
    submitted_payload = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="OPEN")
    resolution = Column(String(40), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "operation_record_id",
            "submission_hash",
            name="uq_offline_conflict_submission",
        ),
        Index("ix_offline_sync_conflicts_status_created", "status", "created_at"),
    )
