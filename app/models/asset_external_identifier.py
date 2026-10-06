from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database.database import Base


class AssetExternalIdentifier(Base):
    __tablename__ = "asset_external_identifiers"

    id = Column(Integer, primary_key=True, index=True)

    asset_registry_id = Column(
        Integer,
        ForeignKey("asset_registry.id"),
        nullable=False,
        index=True,
    )

    authority = Column(String, nullable=False)
    identifier_type = Column(String, nullable=False)
    identifier_value = Column(String, nullable=False)

    status = Column(String, nullable=False, default="ACTIVE")

    source_reference = Column(String, nullable=True)

    verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
