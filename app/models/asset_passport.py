from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class AssetPassport(Base):
    __tablename__ = "asset_passports"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Public/stable SAL Passport identifier.
    # This is separate from the internal database ID.
    passport_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    # One Passport belongs to exactly one Master Registry identity.
    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        unique=True,
        nullable=False,
        index=True
    )

    # Passport lifecycle status.
    status = Column(
        String,
        nullable=False,
        default="ACTIVE"
    )

    # Current high-level lifecycle state.
    lifecycle_state = Column(
        String,
        nullable=False,
        default="REGISTERED"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
