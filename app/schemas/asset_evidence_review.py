from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AssetEvidenceReviewRequest(BaseModel):
    status: str
    expected_version: int
    reason: str | None = None
    reference: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().upper()

        if not value:
            raise ValueError("Status cannot be empty")

        return value

    @field_validator("reason", "reference")
    @classmethod
    def validate_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator("expected_version")
    @classmethod
    def validate_expected_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("expected_version must be at least 1")

        return value


class AssetEvidenceReviewResponse(BaseModel):
    id: int
    evidence_id: str
    passport_id: int

    evidence_type: str
    title: str
    description: str | None = None
    source: str | None = None
    reference: str | None = None

    status: str
    submitted_by: str | None = None
    version: int

    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AssetEvidenceReviewHistoryResponse(BaseModel):
    id: int
    evidence_id: int
    from_status: str
    to_status: str
    reason: str | None = None
    reference: str | None = None
    reviewed_by: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
