from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class IntellectualProperty(Base):
    __tablename__ = "intellectual_properties"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    title = Column(String, nullable=False)
    ip_type = Column(String, nullable=False)  # Patent, Trademark, Copyright
    registration_number = Column(String, unique=True, nullable=False)
    country = Column(String, nullable=False)
    estimated_value = Column(Float, nullable=False)

    status = Column(String, default="Registered")