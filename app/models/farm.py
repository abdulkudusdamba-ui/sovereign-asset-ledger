from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    farm_name = Column(String, nullable=False)
    farm_type = Column(String, nullable=False)   # Crop, Livestock, Mixed
    location = Column(String, nullable=False)
    size_acres = Column(Float, nullable=False)
    estimated_value = Column(Float, nullable=False)

    status = Column(String, default="Registered")