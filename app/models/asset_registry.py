from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func

from app.database.database import Base


class AssetRegistry(Base):

    __tablename__ = "asset_registry"

    id = Column(Integer, primary_key=True, index=True)

    sal_id = Column(String, unique=True, index=True)

    asset_type = Column(String, nullable=False)

    registry_id = Column(Integer, nullable=False)

    owner = Column(String, nullable=False)

    estimated_value = Column(Float, nullable=True)

    status = Column(String, default="Active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )