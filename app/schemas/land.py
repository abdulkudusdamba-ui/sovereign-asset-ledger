from pydantic import BaseModel
from datetime import datetime


class LandBase(BaseModel):
    parcel_number: str
    owner_name: str
    community: str
    district: str
    region: str
    size: float
    land_use: str
    estimated_value: float


class LandCreate(LandBase):
    pass


class LandResponse(LandBase):
    id: int
    approval_status: str
    created_at: datetime

    class Config:
        from_attributes = True