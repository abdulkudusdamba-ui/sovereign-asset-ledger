import json
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


SENSITIVE_KEYS = {
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "api_key",
    "private_key",
    "authorization",
    "cookie",
}


def _sanitize_for_audit(value: Any) -> Any:
    """
    Recursively remove sensitive values before they are stored
    in Audit Trail snapshots or metadata.
    """
    if isinstance(value, dict):
        sanitized = {}

        for key, item in value.items():
            normalized_key = str(key).strip().lower()

            if normalized_key in SENSITIVE_KEYS:
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_for_audit(item)

        return sanitized

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_for_audit(item)
            for item in value
        ]

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def _serialize_audit_data(value: Any) -> str | None:
    if value is None:
        return None

    sanitized = _sanitize_for_audit(value)

    return json.dumps(
        sanitized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def record_audit_event(
    db: Session,
    *,
    actor_id: int | None = None,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str | int,
    asset_registry_id: int | None = None,
    passport_id: int | None = None,
    occurred_at: datetime | None = None,
    source: str,
    device_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
    reference: str | None = None,
    result: str,
    before_data: Any = None,
    after_data: Any = None,
    metadata: Any = None,
) -> AuditEvent:
    """
    Record one immutable SAL Audit Trail event.

    This function intentionally does NOT commit the database
    transaction. The calling business operation owns the
    transaction and must commit the business change together
    with its audit event.
    """

    event = AuditEvent(
        event_id=f"SAL-EVENT-{secrets.token_hex(8).upper()}",
        actor_id=actor_id,
        actor_type=actor_type.strip(),
        action=action.strip(),
        entity_type=entity_type.strip(),
        entity_id=str(entity_id),
        asset_registry_id=asset_registry_id,
        passport_id=passport_id,
        occurred_at=_normalize_datetime(occurred_at),
        source=source.strip(),
        device_id=device_id,
        ip_address=ip_address,
        user_agent=user_agent,
        reason=reason,
        reference=reference,
        result=result.strip(),
        before_data=_serialize_audit_data(before_data),
        after_data=_serialize_audit_data(after_data),
        audit_metadata=_serialize_audit_data(metadata),
    )

    db.add(event)
    db.flush()

    return event
