from pydantic import BaseModel


class BondCreate(BaseModel):
    owner: str
    issuer: str
    bond_type: str
    face_value: float
    interest_rate: float
    maturity_date: str


class BondResponse(BondCreate):
    id: int
    status: str

    class Config:
        from_attributes = True