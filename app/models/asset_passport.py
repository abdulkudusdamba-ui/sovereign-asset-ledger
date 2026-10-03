from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database.database import Base


class AssetPassport(Base):
    __tablename__ = "asset_passports"

    id = Column(Integer, primary_key=True, index=True)

    passport_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    status = Column(
        String,
        nullable=False,
        default="ACTIVE",
    )

    lifecycle_state = Column(
        String,
        nullable=False,
        default="REGISTERED",
    )

    # Optimistic concurrency version.
    #
    # Every successful lifecycle mutation increments this value.
    # A lifecycle update must only succeed if the version read by
    # the caller is still the current database version.
    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
