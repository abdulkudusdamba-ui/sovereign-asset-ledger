from sqlalchemy import Column, Integer, String, Float

from app.database.database import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String)
    asset_name = Column(String)
    value = Column(Float)