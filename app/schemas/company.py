from pydantic import BaseModel

class CompanyBase(BaseModel):
    owner: str
    company_name: str
    registration_number: str
    business_type: str
    country: str
    estimated_value: float


class CompanyCreate(CompanyBase):
    pass


class CompanyResponse(CompanyBase):
    id: int
    status: str

    class Config:
        from_attributes = True