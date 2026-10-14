from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ASSET_TYPES = ("asset", "land", "vehicle", "gold", "diamond")


class OfflineOperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    operation_id: str = Field(min_length=1, max_length=36)
    operation: str = Field(min_length=1, max_length=20)
    asset_type: str = Field(min_length=1, max_length=50)
    data: dict[str, Any]


class OfflineSyncBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    operations: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class OfflineConflictResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    resolution: Literal["reject_submission", "acknowledge_existing"]


class OfflineOperationResult(BaseModel):
    operation_id: str | None
    asset_type: str | None
    status: str
    record_id: int | None = None
    sal_id: str | None = None
    conflict_id: int | None = None
    message: str


class OfflineSyncResponse(BaseModel):
    results: list[OfflineOperationResult]


class OfflineConflictResponse(BaseModel):
    id: int
    operation_id: str
    asset_type: str
    conflict_type: str
    identifier_type: str | None
    identifier_value: str | None
    submitted_payload: dict[str, Any]
    status: str
    resolution: str | None
    created_at: str
