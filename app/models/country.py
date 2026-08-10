from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.database.database import Base


class Country(Base):

    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)

    # ISO-style country code
    code = Column(String(10), unique=True, nullable=False, index=True)

    name = Column(String, nullable=False)

    # Default currency used by the country
    currency = Column(String(10), nullable=False)

    # Whether SAL currently operates in this country
    is_active = Column(Boolean, default=False)

    # Country-specific configuration version
    configuration_version = Column(
        String(50),
        default="1.0"
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
