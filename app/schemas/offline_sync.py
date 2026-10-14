from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OfflineSyncOperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    asset_registry_id: int = Field(gt=0)
    expected_version: int = Field(ge=1)
    changes: dict[str, Any]


class OfflineSyncBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[OfflineSyncOperationRequest] = Field(
        min_length=1,
        max_length=100,
    )


class OfflineSyncOperationResult(BaseModel):
    operation_id: str
    outcome: Literal["ACCEPTED", "REJECTED", "DUPLICATE", "CONFLICT"]
    record_status: str
    conflict_id: int | None = None
    message: str


class OfflineSyncBatchResponse(BaseModel):
    results: list[OfflineSyncOperationResult]


class OfflineSyncConflictResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Literal["ACCEPT", "REJECT"]
    note: str = Field(min_length=1, max_length=1000)


class OfflineSyncConflictResponse(BaseModel):
    id: int
    operation_id: str
    reason: str
    status: str
    resolution: str | None
    resolution_note: str | None
    resolved_by: int | None

    model_config = ConfigDict(from_attributes=True)
