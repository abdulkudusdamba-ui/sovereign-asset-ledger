from pydantic import BaseModel
from typing import Optional


class VehicleCreate(BaseModel):
    owner: str
    registration_number: str
    vin: str
    manufacturer: str
    model: str
    year: int
    engine_number: str
    color: str
    estimated_value: float
    chassis_number: Optional[str] = None


class VehicleResponse(VehicleCreate):
    id: int
    status: str

    class Config:
        from_attributes = True