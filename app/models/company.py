from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    registration_number = Column(String, unique=True, nullable=False)
    business_type = Column(String, nullable=False)
    country = Column(String, nullable=False)
    estimated_value = Column(Float, nullable=False)

    status = Column(String, default="Registered")