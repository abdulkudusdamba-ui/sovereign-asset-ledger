from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.database import Base


class Pricing(Base):

    __tablename__ = "pricing"

    id = Column(Integer, primary_key=True, index=True)

    service_name = Column(String, nullable=False)

    country_id = Column(
        Integer,
        ForeignKey("countries.id"),
        nullable=False
    )

    currency = Column(String(10), nullable=False)

    amount = Column(Float, nullable=False)

    billing_type = Column(
        String,
        default="ONE_TIME"
    )

    tax_percent = Column(
        Float,
        default=0.0
    )

    discount_percent = Column(
        Float,
        default=0.0
    )

    active = Column(
        Boolean,
        default=True
    )

    effective_from = Column(
        DateTime(timezone=True),
        server_default=func.now()
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
