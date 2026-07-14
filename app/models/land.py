from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

from app.database.database import Base

class Land(Base):
    __tablename__ = "lands"

    id = Column(Integer, primary_key=True, index=True)
    parcel_number = Column(String, unique=True, nullable=False)
    owner_name = Column(String, nullable=False)
    community = Column(String, nullable=False)
    district = Column(String, nullable=False)
    region = Column(String, nullable=False)
    size = Column(Float, nullable=False)
    land_use = Column(String, nullable=False)
    estimated_value = Column(Float, nullable=False, default=0)
    approval_status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)