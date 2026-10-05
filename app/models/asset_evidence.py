from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class AssetEvidence(Base):
    """
    Evidence metadata attached to a SAL Asset Passport.

    Evidence supports verification workflows but does not, by itself,
    establish legal ownership or government title.

    File content is stored through the Evidence Storage Service.
    This table stores only the metadata required to locate, identify,
    and verify that stored content.
    """

    __tablename__ = "asset_evidence"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    evidence_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    passport_id = Column(
        Integer,
        ForeignKey("asset_passports.id"),
        nullable=False,
        index=True,
    )

    evidence_type = Column(
        String,
        nullable=False,
    )

    title = Column(
        String,
        nullable=False,
    )

    description = Column(
        String,
        nullable=True,
    )

    source = Column(
        String,
        nullable=True,
    )

    reference = Column(
        String,
        nullable=True,
        index=True,
    )

    fingerprint_sha256 = Column(
        String(64),
        nullable=True,
        index=True,
    )

    storage_backend = Column(
        String,
        nullable=True,
        index=True,
    )

    storage_key = Column(
        String,
        nullable=True,
        index=True,
    )

    original_filename = Column(
        String,
        nullable=True,
    )

    content_type = Column(
        String,
        nullable=True,
    )

    size_bytes = Column(
        Integer,
        nullable=True,
    )

    status = Column(
        String,
        nullable=False,
        default="SUBMITTED",
    )

    submitted_by = Column(
        String,
        nullable=True,
    )

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
