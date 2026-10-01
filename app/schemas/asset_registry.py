from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AssetRegistryCreate(BaseModel):
    """
    Data required to create a SAL master registry record.

    SAL ID is generated server-side.
    Clients cannot provide or override the SAL ID.
    """

    model_config = ConfigDict(extra="forbid")

    asset_type: str
    registry_id: int
    owner: str
    estimated_value: Optional[float] = 0.0
    status: str = "Active"


class AssetRegistryResponse(BaseModel):
    id: int
    sal_id: str
    asset_type: str
    registry_id: int
    owner: str
    estimated_value: Optional[float]
    status: str
    sal_verification: str
    government_verification: str
    blockchain_status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
