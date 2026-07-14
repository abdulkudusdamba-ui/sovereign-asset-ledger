from pydantic import BaseModel

class DiamondCreate(BaseModel):
    owner: str
    gemstone: str
    carat: float
    cut: str
    color: str
    clarity: str
    certificate_number: str
    estimated_value: float


class DiamondResponse(DiamondCreate):
    id: int
    status: str

    class Config:
        from_attributes = True