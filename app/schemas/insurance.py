from pydantic import BaseModel
from datetime import date


class InsuranceCreate(BaseModel):
    owner: str
    asset_type: str
    asset_id: int
    insurer: str
    policy_number: str
    premium: float
    coverage_amount: float
    start_date: date
    end_date: date


class InsuranceResponse(InsuranceCreate):
    id: int
    status: str

    class Config:
        from_attributes = True