from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from app.database.database import Base


ACTIVE_JOB_STATUS_SQL = "status IN ('PENDING', 'IN_PROGRESS')"


class VehicleVerificationJob(Base):
    """
    Lifecycle record for one vehicle identity check against an
    authority provider.

    All state, outcome and attempt fields are server-controlled.
    A job outcome is NOT government verification, proof of ownership
    or a DVLA confirmation, and it never updates
    AssetRegistry.government_verification or GovernmentVerification.

    The job stores no owner information and no raw provider payload.
    """

    __tablename__ = "vehicle_verification_jobs"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(String, unique=True, nullable=False, index=True)

    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        nullable=False,
        index=True,
    )

    provider = Column(String, nullable=False)

    # PENDING, IN_PROGRESS, COMPLETED, FAILED
    status = Column(String, nullable=False, default="PENDING")

    # MATCH or MISMATCH; only set when status is COMPLETED.
    outcome = Column(String, nullable=True)

    # Comma-separated field names that did not match.
    mismatched_fields = Column(String, nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0)

    requested_by = Column(Integer, nullable=True)

    idempotency_key = Column(String, nullable=True)

    lease_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Coded error only; never untrusted provider text.
    last_error_code = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="ck_vehicle_verification_jobs_status",
        ),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_vehicle_verification_jobs_user_key",
        ),
        Index(
            "uq_vehicle_verification_jobs_one_active",
            "asset_registry_id",
            "provider",
            unique=True,
            postgresql_where=text(ACTIVE_JOB_STATUS_SQL),
            sqlite_where=text(ACTIVE_JOB_STATUS_SQL),
        ),
    )
