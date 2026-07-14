from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base

class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    bank_name = Column(String, nullable=False)
    account_number = Column(String, unique=True, nullable=False)
    account_type = Column(String, nullable=False)   # Savings, Current
    currency = Column(String, nullable=False)       # GHS, USD, EUR
    balance = Column(Float, default=0.0)

    status = Column(String, default="Registered")