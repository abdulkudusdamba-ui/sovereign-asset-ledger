from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base

class Diamond(Base):
    __tablename__ = "diamonds"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    gemstone = Column(String, nullable=False)      # Diamond, Ruby, Emerald, Sapphire
    carat = Column(Float, nullable=False)
    cut = Column(String, nullable=False)
    color = Column(String, nullable=False)
    clarity = Column(String, nullable=False)
    certificate_number = Column(String, unique=True, nullable=False)
    estimated_value = Column(Float, nullable=False)

    status = Column(String, default="Registered")