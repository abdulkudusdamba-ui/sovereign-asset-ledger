from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class Bond(Base):
    __tablename__ = "bonds"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)
    issuer = Column(String, nullable=False)
    bond_type = Column(String, nullable=False)
    face_value = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)
    maturity_date = Column(String, nullable=False)

    status = Column(String, default="Registered")