from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    id: int
    event_id: str
    actor_id: int | None = None
    actor_type: str
    action: str
    entity_type: str
    entity_id: str
    asset_registry_id: int | None = None
    passport_id: int | None = None
    occurred_at: datetime
    received_at: datetime
    source: str
    device_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    reason: str | None = None
    reference: str | None = None
    result: str
    before_data: str | None = None
    after_data: str | None = None
    audit_metadata: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
