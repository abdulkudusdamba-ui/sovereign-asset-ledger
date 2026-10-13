from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.models.audit_event import AuditEvent
from app.models.provenance_commitment import ProvenanceCommitment
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
        raise HTTPException(status_code=404, detail="Accepted SAL event not found")

    existing = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.event_id == event_id)
        .first()
    )
    if existing:
        return commitment_metadata(existing)

    try:
        commitment = create_commitment(db, event)
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
    db.commit()
    db.refresh(commitment)
    return commitment_metadata(commitment)
