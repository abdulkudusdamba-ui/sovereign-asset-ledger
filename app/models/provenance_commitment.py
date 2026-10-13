from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database.database import Base


class ProvenanceCommitment(Base):
    __tablename__ = "provenance_commitments"

    id = Column(Integer, primary_key=True)
    commitment_id = Column(String, unique=True, nullable=False, index=True)
    event_id = Column(
        String,
        ForeignKey("audit_events.event_id"),
        unique=True,
        nullable=False,
        index=True,
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
    record_version = Column(Integer, nullable=False)
    format_version = Column(Integer, nullable=False)
    previous_commitment_id = Column(String, nullable=True)
    commitment_hash = Column(String(64), nullable=False)
    nonce = Column(String(64), nullable=False)
    signature = Column(String, nullable=True)
    signer_key_id = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ledger_provider = Column(String, nullable=False)
    network_id = Column(String, nullable=False)
    anchor_status = Column(
        String,
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )
    anchor_reference = Column(String, nullable=True)
    anchor_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_anchor_error = Column(String, nullable=True)


class ProvenanceAnchorAttempt(Base):
    __tablename__ = "provenance_anchor_attempts"

    id = Column(Integer, primary_key=True)
    commitment_id = Column(
        Integer,
        ForeignKey("provenance_commitments.id"),
        nullable=False,
        index=True,
    )
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False)
    anchor_reference = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    attempted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
