from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class GovernmentVerification(Base):

    __tablename__ = "government_verifications"

    id = Column(Integer, primary_key=True, index=True)

    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        nullable=False,
        index=True
    )

    authority = Column(
        String,
        nullable=True
    )

    reference_number = Column(
        String,
        nullable=True
    )

    status = Column(
        String,
        default="PENDING"
    )

    verified_by = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    requested_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    verified_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
