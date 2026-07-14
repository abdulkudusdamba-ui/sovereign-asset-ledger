from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    business_name = Column(String, nullable=False)
    business_type = Column(String, nullable=False)
    registration_number = Column(String, unique=True, nullable=False)
    address = Column(String, nullable=False)
    annual_revenue = Column(Float, nullable=False)

    status = Column(String, default="Registered")