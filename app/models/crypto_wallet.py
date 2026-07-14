from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class CryptoWallet(Base):
    __tablename__ = "crypto_wallets"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    wallet_name = Column(String, nullable=False)
    blockchain = Column(String, nullable=False)
    wallet_address = Column(String, unique=True, nullable=False)
    cryptocurrency = Column(String, nullable=False)
    balance = Column(Float, nullable=False)
    estimated_value = Column(Float, nullable=False)

    status = Column(String, default="Registered")