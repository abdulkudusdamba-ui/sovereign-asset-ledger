from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    ticker_symbol = Column(String, nullable=False)
    shares = Column(Float, nullable=False)
    share_price = Column(Float, nullable=False)
    estimated_value = Column(Float, nullable=False)

    status = Column(String, default="Registered")