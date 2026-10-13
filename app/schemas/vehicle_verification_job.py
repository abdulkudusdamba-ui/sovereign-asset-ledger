from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VehicleVerificationJobCreate(BaseModel):
    """Client input is limited to the SAL ID; all else is server-set."""

    model_config = ConfigDict(extra="forbid")

    sal_id: str = Field(min_length=1, max_length=100)


class VehicleVerificationJobResponse(BaseModel):
    """
    Job state. Contains no owner data and no raw provider payload.
    A MATCH outcome is not government verification or ownership proof.
    """

    job_id: str
    sal_id: str | None
    status: str
    outcome: str | None
    mismatched_fields: list[str]
    provider: str
    attempt_count: int
    last_error_code: str | None
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
