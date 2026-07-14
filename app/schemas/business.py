from pydantic import BaseModel


class BusinessCreate(BaseModel):
    owner: str
    business_name: str
    business_type: str
    registration_number: str
    address: str
    annual_revenue: float


class BusinessResponse(BusinessCreate):
    id: int
    status: str

    class Config:
        from_attributes = True