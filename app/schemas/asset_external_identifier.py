from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetExternalIdentifierCreate(BaseModel):
    asset_registry_id: int = Field(gt=0)
    authority: str = Field(min_length=1, max_length=100)
    identifier_type: str = Field(min_length=1, max_length=100)
    identifier_value: str = Field(min_length=1, max_length=255)
    status: str = Field(default="ACTIVE", min_length=1, max_length=50)
    source_reference: str | None = Field(
        default=None,
        max_length=255,
    )
    verified_at: datetime | None = None
    reason: str | None = Field(
        default=None,
        max_length=500,
    )
    reference: str | None = Field(
        default=None,
        max_length=255,
    )


class AssetExternalIdentifierStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=50)
    reason: str | None = Field(
        default=None,
        max_length=500,
    )
    reference: str | None = Field(
        default=None,
        max_length=255,
    )


class AssetExternalIdentifierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_registry_id: int
    authority: str
    identifier_type: str
    identifier_value: str
    status: str
    source_reference: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssetExternalIdentifierLookupResponse(BaseModel):
    sal_id: str | None
    asset_registry_id: int
    asset_type: str
    owner: str
    identifier: AssetExternalIdentifierResponse
