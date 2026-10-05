from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from app.database.database import Base


class AssetEvidenceReviewHistory(Base):
    """
    Immutable history of SAL Evidence review-state transitions.

    This records SAL's internal evidence-review workflow.
    It does not itself establish legal ownership or government title.
    """

    __tablename__ = "asset_evidence_review_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    evidence_id = Column(
        Integer,
        ForeignKey("asset_evidence.id"),
        nullable=False,
        index=True,
    )

    from_status = Column(
        String,
        nullable=False,
    )

    to_status = Column(
        String,
        nullable=False,
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

    reviewed_by = Column(
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
            "uq_asset_evidence_review_history_reference",
            "reference",
            unique=True,
            sqlite_where=reference.isnot(None),
        ),
    )
