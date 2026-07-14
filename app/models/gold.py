from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base

class Gold(Base):
    __tablename__ = "gold"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String)
    type = Column(String)          # Bar, Coin, Jewelry
    purity = Column(String)        # 24K, 22K, etc.
    weight = Column(Float)         # grams
    estimated_value = Column(Float)
    serial_number = Column(String, unique=True)
    status = Column(String, default="Registered")