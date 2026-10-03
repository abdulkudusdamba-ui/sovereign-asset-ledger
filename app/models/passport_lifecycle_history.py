from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class PassportLifecycleHistory(Base):
    __tablename__ = "passport_lifecycle_history"

    id = Column(Integer, primary_key=True, index=True)

    passport_id = Column(
        Integer,
        ForeignKey("asset_passports.id"),
        nullable=False,
        index=True,
    )

    from_state = Column(
        String,
        nullable=False,
    )

    to_state = Column(
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
    )

    changed_by = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
