from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.models.audit_event import AuditEvent
from app.models.provenance_commitment import (
    ProvenanceAnchorAttempt,
    ProvenanceCommitment,
)
from app.services.audit_service import record_audit_event
from app.services.provenance_service import (
    commitment_metadata,
    create_commitment,
    process_anchor,
    verify_commitment,
)


router = APIRouter(prefix="/provenance", tags=["Blockchain Provenance"])
PROVENANCE_ROLES = ["admin", "registrar", "government"]


@router.post(
    "/events/{event_id}/commitment",
    status_code=status.HTTP_201_CREATED,
)
def create_event_commitment(
    event_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(PROVENANCE_ROLES)),
):
    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_id == event_id)
        .first()
    )
    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Accepted SAL event not found",
        )

    existing = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.event_id == event_id)
        .first()
    )
    if existing:
        return commitment_metadata(existing)

    try:
        commitment = create_commitment(db, event)
        record_audit_event(
            db,
            actor_id=current_user.id,
            actor_type="USER",
            action="PROVENANCE_COMMITMENT_CREATED",
            entity_type="PROVENANCE_COMMITMENT",
            entity_id=commitment.commitment_id,
            asset_registry_id=commitment.asset_registry_id,
            passport_id=commitment.passport_id,
            source="API",
            reference=event.event_id,
            result="SUCCESS",
            metadata={
                "format_version": commitment.format_version,
                "commitment_hash": commitment.commitment_hash,
                "signer_key_id": commitment.signer_key_id,
            },
        )
        db.commit()
        db.refresh(commitment)
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(ProvenanceCommitment)
            .filter(ProvenanceCommitment.event_id == event_id)
            .first()
        )
        if existing is None:
            raise HTTPException(
                status_code=409,
                detail="Commitment could not be created",
            ) from exc
        return commitment_metadata(existing)

    process_anchor(db, commitment)
    db.commit()
    db.refresh(commitment)
    return commitment_metadata(commitment)


@router.get("/passports/{passport_id}/commitments")
def list_passport_commitments(
    passport_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(PROVENANCE_ROLES)),
):
    commitments = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.passport_id == passport_id)
        .order_by(ProvenanceCommitment.id.asc())
        .all()
    )
    return [commitment_metadata(commitment) for commitment in commitments]


@router.get("/commitments/{commitment_id}")
def get_commitment(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(PROVENANCE_ROLES)),
):
    commitment = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.commitment_id == commitment_id)
        .first()
    )
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return commitment_metadata(commitment)


@router.get("/commitments/{commitment_id}/attempts")
def list_anchor_attempts(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(PROVENANCE_ROLES)),
):
    commitment = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.commitment_id == commitment_id)
        .first()
    )
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    attempts = (
        db.query(ProvenanceAnchorAttempt)
        .filter(ProvenanceAnchorAttempt.commitment_id == commitment.id)
        .order_by(ProvenanceAnchorAttempt.id.asc())
        .all()
    )
    return [
        {
            "provider": attempt.provider,
            "status": attempt.status,
            "anchor_reference": attempt.anchor_reference,
            "error_code": attempt.error_code,
            "attempted_at": attempt.attempted_at,
        }
        for attempt in attempts
    ]


@router.get("/commitments/{commitment_id}/verify")
def verify_stored_commitment(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(PROVENANCE_ROLES)),
):
    commitment = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.commitment_id == commitment_id)
        .first()
    )
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return verify_commitment(db, commitment)


@router.post("/commitments/{commitment_id}/retry")
def retry_commitment_anchor(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    commitment = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.commitment_id == commitment_id)
        .first()
    )
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    if commitment.anchor_status == "CONFIRMED":
        return commitment_metadata(commitment)

    process_anchor(db, commitment)
    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_type="USER",
        action="PROVENANCE_ANCHOR_ATTEMPT",
        entity_type="PROVENANCE_COMMITMENT",
        entity_id=commitment.commitment_id,
        asset_registry_id=commitment.asset_registry_id,
        passport_id=commitment.passport_id,
        source="API",
        reference=commitment.event_id,
        result=commitment.anchor_status,
        metadata={
            "provider": commitment.ledger_provider,
            "attempt": commitment.anchor_attempts,
            "anchor_reference": commitment.anchor_reference,
        },
    )
    db.commit()
    db.refresh(commitment)
    return commitment_metadata(commitment)
