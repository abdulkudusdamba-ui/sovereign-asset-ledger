from pydantic import BaseModel


class FarmCreate(BaseModel):
    owner: str
    farm_name: str
    farm_type: str
    location: str
    size_acres: float
    estimated_value: float


class FarmResponse(FarmCreate):
    id: int
    status: str

    class Config:
        from_attributes = True