from sqlalchemy import Column, Integer, String, Float

from app.database.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)

    registration_number = Column(String, unique=True, nullable=False)

    vin = Column(String, unique=True, nullable=False)

    manufacturer = Column(String)

    model = Column(String)

    year = Column(Integer)

    engine_number = Column(String)

    color = Column(String)

    estimated_value = Column(Float)

    status = Column(String, default="ACTIVE")