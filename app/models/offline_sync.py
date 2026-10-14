from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database.database import Base


class OfflineSyncOperation(Base):
    __tablename__ = "offline_sync_operations"

    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(String(64), nullable=False, unique=True, index=True)
    actor_id = Column(Integer, nullable=False, index=True)
    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        nullable=True,
        index=True,
    )
    payload = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OfflineSyncConflict(Base):
    __tablename__ = "offline_sync_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    operation_record_id = Column(
        Integer,
        ForeignKey("offline_sync_operations.id"),
        nullable=True,
        index=True,
    )
    operation_id = Column(String(64), nullable=False, index=True)
    submitted_by = Column(Integer, nullable=False, index=True)
    submission_payload = Column(Text, nullable=False)
    reason = Column(String(40), nullable=False)
    status = Column(String(16), nullable=False, default="PENDING")
    resolution = Column(String(16), nullable=True)
    resolution_note = Column(String(1000), nullable=True)
    resolved_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
