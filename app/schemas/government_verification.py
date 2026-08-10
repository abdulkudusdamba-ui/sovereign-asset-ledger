from pydantic import BaseModel
from typing import Optional


class GovernmentVerificationCreate(BaseModel):
    asset_registry_id: int
    authority: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class GovernmentVerificationResponse(BaseModel):
    id: int
    asset_registry_id: int
    authority: Optional[str]
    reference_number: Optional[str]
    status: str
    verified_by: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True
class GovernmentVerificationDecision(BaseModel):
    status: str
    verified_by: str
    notes: Optional[str] = None
