from enum import Enum

from sqlalchemy.orm import Session

from app.models.asset_evidence import AssetEvidence
from app.models.asset_evidence_review_history import (
    AssetEvidenceReviewHistory,
)


class AssetEvidenceStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


ALLOWED_EVIDENCE_TRANSITIONS = {
    AssetEvidenceStatus.SUBMITTED: {
        AssetEvidenceStatus.UNDER_REVIEW,
    },
    AssetEvidenceStatus.UNDER_REVIEW: {
        AssetEvidenceStatus.VERIFIED,
        AssetEvidenceStatus.REJECTED,
    },
    AssetEvidenceStatus.VERIFIED: set(),
    AssetEvidenceStatus.REJECTED: set(),
}


class AssetEvidenceReviewTransitionError(Exception):
    """Raised when an Evidence review transition is invalid."""


class AssetEvidenceNotFoundError(Exception):
    """Raised when the requested Evidence does not exist."""


class AssetEvidenceConcurrencyError(Exception):
    """Raised when Evidence was changed by another transaction."""


def is_valid_evidence_transition(
    current_status: AssetEvidenceStatus,
    requested_status: AssetEvidenceStatus,
) -> bool:
    return requested_status in ALLOWED_EVIDENCE_TRANSITIONS.get(
        current_status,
        set(),
    )


def transition_asset_evidence(
    db: Session,
    evidence_id: str,
    new_status: str | AssetEvidenceStatus,
    expected_version: int | None = None,
    reason: str | None = None,
    reference: str | None = None,
    reviewed_by: str | None = None,
) -> AssetEvidence:
    evidence = (
        db.query(AssetEvidence)
        .filter(AssetEvidence.evidence_id == evidence_id)
        .first()
    )

    if not evidence:
        raise AssetEvidenceNotFoundError(
            f"Evidence {evidence_id} was not found"
        )

    if (
        expected_version is not None
        and expected_version != evidence.version
    ):
        raise AssetEvidenceConcurrencyError(
            f"Evidence {evidence.evidence_id} version conflict: "
            f"expected {expected_version}, current {evidence.version}"
        )

    try:
        current_status = AssetEvidenceStatus(
            evidence.status
        )
    except ValueError as exc:
        raise AssetEvidenceReviewTransitionError(
            f"Evidence {evidence.evidence_id} has an invalid "
            f"current status: {evidence.status}"
        ) from exc

    try:
        requested_status = AssetEvidenceStatus(new_status)
    except ValueError as exc:
        raise AssetEvidenceReviewTransitionError(
            f"Invalid Evidence status: {new_status}"
        ) from exc

    if current_status == requested_status:
        raise AssetEvidenceReviewTransitionError(
            f"Evidence {evidence.evidence_id} is already in "
            f"{requested_status.value}"
        )

    if not is_valid_evidence_transition(
        current_status,
        requested_status,
    ):
        raise AssetEvidenceReviewTransitionError(
            f"Invalid Evidence review transition: "
            f"{current_status.value} -> {requested_status.value}"
        )

    if expected_version is None:
        raise AssetEvidenceConcurrencyError(
            f"Evidence {evidence.evidence_id} requires an expected version"
        )

    updated_rows = (
        db.query(AssetEvidence)
        .filter(
            AssetEvidence.id == evidence.id,
            AssetEvidence.version == expected_version,
            AssetEvidence.status == current_status.value,
        )
        .update(
            {
                AssetEvidence.status: requested_status.value,
                AssetEvidence.version: expected_version + 1,
            },
            synchronize_session=False,
        )
    )

    if updated_rows != 1:
        raise AssetEvidenceConcurrencyError(
            f"Evidence {evidence.evidence_id} was modified by another "
            f"transaction; review update was rejected"
        )

    history = AssetEvidenceReviewHistory(
        evidence_id=evidence.id,
        from_status=current_status.value,
        to_status=requested_status.value,
        reason=reason,
        reference=reference,
        reviewed_by=reviewed_by,
    )

    db.add(history)
    db.flush()

    db.refresh(evidence)

    return evidence
