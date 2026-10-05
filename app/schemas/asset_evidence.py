from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AssetEvidenceCreate(BaseModel):
    evidence_type: str
    title: str
    description: str | None = None
    source: str | None = None
    reference: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_type", "title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty")

        return value


class AssetEvidenceResponse(BaseModel):
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
