from pydantic import BaseModel

class AssetCreate(BaseModel):
    owner: str
    asset_name: str
    value: float

class AssetResponse(AssetCreate):
    id: int

    class Config:
        from_attributes = True