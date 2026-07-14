from pydantic import BaseModel

class GoldCreate(BaseModel):
    owner: str
    type: str
    purity: str
    weight: float
    estimated_value: float
    serial_number: str

class GoldResponse(GoldCreate):
    id: int
    status: str

    class Config:
        from_attributes = True