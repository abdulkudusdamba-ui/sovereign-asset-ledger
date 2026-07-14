from pydantic import BaseModel


class AssetRegistryCreate(BaseModel):

    sal_id: str

    asset_type: str

    registry_id: int

    owner: str

    estimated_value: float

    status: str = "Active"


class AssetRegistryResponse(AssetRegistryCreate):

    id: int

    class Config:
        from_attributes = True