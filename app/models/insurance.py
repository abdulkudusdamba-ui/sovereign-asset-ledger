from sqlalchemy import Column, Integer, String, Float, Date
from app.database.database import Base


class Insurance(Base):
    __tablename__ = "insurance"

    id = Column(Integer, primary_key=True, index=True)

    owner = Column(String, nullable=False)

    asset_type = Column(String, nullable=False)
    asset_id = Column(Integer, nullable=False)

    insurer = Column(String, nullable=False)

    policy_number = Column(String, unique=True, nullable=False)

    premium = Column(Float, nullable=False)

    coverage_amount = Column(Float, nullable=False)

    start_date = Column(Date)

    end_date = Column(Date)

    status = Column(String, default="Active")