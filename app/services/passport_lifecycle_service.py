from enum import Enum

from sqlalchemy.orm import Session

from app.models.asset_passport import AssetPassport
from app.models.asset_registry import AssetRegistry
from app.models.passport_lifecycle_history import PassportLifecycleHistory
from app.services.audit_service import record_audit_event


class PassportLifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    TRANSFERRED = "TRANSFERRED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


PASSPORT_LIFECYCLE_SEMANTICS = {
    PassportLifecycleState.REGISTERED: {
        "description": "The Asset Passport has been created and linked to a SAL asset identity, but the Passport has not yet entered its active operational lifecycle.",
        "operational_meaning": "Passport record exists; initial lifecycle activation is pending.",
        "legal_implication": "Does not by itself establish, transfer, or certify legal ownership.",
    },
    PassportLifecycleState.ACTIVE: {
        "description": "The Asset Passport is operational and may participate in supported SAL lifecycle workflows.",
        "operational_meaning": "Normal Passport lifecycle operations are available subject to authorization and verification rules.",
        "legal_implication": "Does not by itself establish, transfer, or certify legal ownership.",
    },
    PassportLifecycleState.TRANSFER_PENDING: {
        "description": "A transfer workflow has been initiated but has not yet reached its completed transfer state.",
        "operational_meaning": "The Passport is undergoing a controlled transfer process; finalization requires an authorized lifecycle transition.",
        "legal_implication": "Does not by itself mean legal ownership has transferred.",
    },
    PassportLifecycleState.TRANSFERRED: {
        "description": "The SAL transfer workflow has reached its completed transfer state.",
        "operational_meaning": "The transfer workflow is recorded as completed in SAL and the Passport can subsequently be reactivated for supported lifecycle operations.",
        "legal_implication": "SAL records a completed SAL workflow; it does not by itself constitute government registration, conveyance, or legal proof of ownership.",
    },
    PassportLifecycleState.SUSPENDED: {
        "description": "Passport operations have been temporarily restricted by an authorized lifecycle action.",
        "operational_meaning": "The Passport is restricted pending recovery, review, or another authorized outcome.",
        "legal_implication": "Suspension is a SAL operational control and does not by itself determine legal ownership or title.",
    },
    PassportLifecycleState.RETIRED: {
        "description": "The Asset Passport has reached a terminal SAL lifecycle state.",
        "operational_meaning": "No further lifecycle transitions are permitted through the current transition model.",
        "legal_implication": "Retirement is a SAL record/lifecycle state and does not by itself extinguish, transfer, or determine legal rights to the underlying asset.",
    },
}


ALLOWED_PASSPORT_TRANSITIONS = {
    PassportLifecycleState.REGISTERED: {
        PassportLifecycleState.ACTIVE,
    },
    PassportLifecycleState.ACTIVE: {
        PassportLifecycleState.TRANSFER_PENDING,
        PassportLifecycleState.SUSPENDED,
        PassportLifecycleState.RETIRED,
    },
    PassportLifecycleState.TRANSFER_PENDING: {
        PassportLifecycleState.TRANSFERRED,
        PassportLifecycleState.ACTIVE,
    },
    PassportLifecycleState.TRANSFERRED: {
        PassportLifecycleState.ACTIVE,
    },
    PassportLifecycleState.SUSPENDED: {
        PassportLifecycleState.ACTIVE,
        PassportLifecycleState.RETIRED,
    },
    PassportLifecycleState.RETIRED: set(),
}


class PassportLifecycleTransitionError(Exception):
    """Raised when a Passport lifecycle transition is invalid."""


class PassportNotFoundError(Exception):
    """Raised when the requested Passport does not exist."""


class PassportConcurrencyError(Exception):
    """Raised when a Passport was changed by another transaction."""


def get_passport_lifecycle_semantics() -> dict[str, dict[str, str]]:
    """Return the controlled operational meaning of each Passport lifecycle state."""
    return {
        state.value: dict(details)
        for state, details in PASSPORT_LIFECYCLE_SEMANTICS.items()
    }


def is_valid_passport_transition(
    current_state: PassportLifecycleState,
    requested_state: PassportLifecycleState,
) -> bool:
    return requested_state in ALLOWED_PASSPORT_TRANSITIONS.get(
        current_state,
        set(),
    )


def transition_passport_lifecycle(
    db: Session,
    passport_id: int,
    new_state: str | PassportLifecycleState,
    expected_version: int | None = None,
    reason: str | None = None,
    reference: str | None = None,
    changed_by: str | None = None,
    actor_id: int | None = None,
    actor_type: str = "USER",
    source: str = "API",
) -> AssetPassport:
    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.id == passport_id)
        .first()
    )

    if not passport:
        raise PassportNotFoundError(
            f"Asset Passport {passport_id} was not found"
        )

    if (
        expected_version is not None
        and expected_version != passport.version
    ):
        raise PassportConcurrencyError(
            f"Passport {passport.id} version conflict: "
            f"expected {expected_version}, current {passport.version}"
        )

    try:
        current_state = PassportLifecycleState(
            passport.lifecycle_state
        )
    except ValueError as exc:
        raise PassportLifecycleTransitionError(
            f"Passport {passport.id} has an invalid current "
            f"lifecycle state: {passport.lifecycle_state}"
        ) from exc

    try:
        requested_state = PassportLifecycleState(new_state)
    except ValueError as exc:
        raise PassportLifecycleTransitionError(
            f"Invalid Passport lifecycle state: {new_state}"
        ) from exc

    if current_state == requested_state:
        raise PassportLifecycleTransitionError(
            f"Passport {passport.id} is already in "
            f"{requested_state.value}"
        )

    if not is_valid_passport_transition(
        current_state,
        requested_state,
    ):
        raise PassportLifecycleTransitionError(
            f"Invalid Passport lifecycle transition: "
            f"{current_state.value} -> {requested_state.value}"
        )

    # Use the caller-provided expected version directly.
    #
    # The final UPDATE below will only succeed if the exact
    # version supplied by the caller is still current.
    if expected_version is None:
        raise PassportConcurrencyError(
            f"Passport {passport.id} requires an expected version"
        )

    updated_rows = (
        db.query(AssetPassport)
        .filter(
            AssetPassport.id == passport.id,
            AssetPassport.version == expected_version,
            AssetPassport.lifecycle_state == current_state.value,
        )
        .update(
            {
                AssetPassport.lifecycle_state: requested_state.value,
                AssetPassport.version: expected_version + 1,
            },
            synchronize_session=False,
        )
    )

    if updated_rows != 1:
        raise PassportConcurrencyError(
            f"Passport {passport.id} was modified by another "
            f"transaction; lifecycle update was rejected"
        )

    history = PassportLifecycleHistory(
        passport_id=passport.id,
        from_state=current_state.value,
        to_state=requested_state.value,
        reason=reason,
        reference=reference,
        changed_by=changed_by,
    )

    db.add(history)

    asset_registry = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == passport.asset_registry_id)
        .first()
    )

    if not asset_registry:
        raise PassportLifecycleTransitionError(
            f"Passport {passport.id} exists, but linked SAL asset "
            "identity was not found"
        )

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_type=actor_type,
        action="PASSPORT_LIFECYCLE",
        entity_type="ASSET_PASSPORT",
        entity_id=passport.passport_id,
        asset_registry_id=asset_registry.id,
        passport_id=passport.id,
        source=source,
        reason=reason,
        reference=reference,
        result="SUCCESS",
        before_data={
            "lifecycle_state": current_state.value,
            "version": expected_version,
        },
        after_data={
            "lifecycle_state": requested_state.value,
            "version": expected_version + 1,
        },
        metadata={
            "changed_by": changed_by,
            "passport_id": passport.passport_id,
            "sal_id": asset_registry.sal_id,
            "asset_type": asset_registry.asset_type,
        },
    )

    db.flush()

    # Refresh the in-memory Passport so the caller receives
    # the new lifecycle state and incremented version.
    db.refresh(passport)

    return passport
