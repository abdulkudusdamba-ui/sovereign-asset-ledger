from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetPassportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetPassportResponse(BaseModel):
    id: int
    passport_id: str
    asset_registry_id: int

    sal_id: str
    asset_type: str
    owner: str
    estimated_value: float | None
    asset_status: str

    status: str
    lifecycle_state: str

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
