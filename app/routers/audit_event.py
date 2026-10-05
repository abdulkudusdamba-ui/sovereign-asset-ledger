from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.models.audit_event import AuditEvent
from app.schemas.audit_event import AuditEventResponse


router = APIRouter(
    prefix="/audit",
    tags=["Audit Trail"],
)


@router.get(
    "/events",
    response_model=list[AuditEventResponse],
)
def list_audit_events(
    asset_registry_id: int | None = Query(default=None, ge=1),
    passport_id: int | None = Query(default=None, ge=1),
    actor_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    entity_type: str | None = Query(default=None, min_length=1, max_length=100),
    entity_id: str | None = Query(default=None, min_length=1, max_length=200),
    reference: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(["admin", "registrar", "government"])
    ),
):
    query = db.query(AuditEvent)

    if asset_registry_id is not None:
        query = query.filter(
            AuditEvent.asset_registry_id == asset_registry_id
        )

    if passport_id is not None:
        query = query.filter(
            AuditEvent.passport_id == passport_id
        )

    if actor_id is not None:
        query = query.filter(
            AuditEvent.actor_id == actor_id
        )

    if action is not None:
        query = query.filter(
            AuditEvent.action == action.strip()
        )

    if entity_type is not None:
        query = query.filter(
            AuditEvent.entity_type == entity_type.strip()
        )

    if entity_id is not None:
        query = query.filter(
            AuditEvent.entity_id == entity_id.strip()
        )

    if reference is not None:
        query = query.filter(
            AuditEvent.reference == reference.strip()
        )

    return (
        query
        .order_by(
            AuditEvent.occurred_at.desc(),
            AuditEvent.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
