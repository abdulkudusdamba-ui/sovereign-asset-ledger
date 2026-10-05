from pydantic import BaseModel, ConfigDict


class AssetEvidenceIntegrityResponse(BaseModel):
    evidence_id: str
    recorded_fingerprint_sha256: str
    stored_fingerprint_sha256: str | None
    result: str

    model_config = ConfigDict(extra="forbid")
