from sqlalchemy.orm import Session

from app.enums.passport_lifecycle import (
    PassportLifecycleState,
    is_valid_passport_transition,
)
from app.models.asset_passport import AssetPassport


class PassportLifecycleTransitionError(Exception):
    """Raised when a Passport lifecycle transition is invalid."""


class PassportNotFoundError(Exception):
    """Raised when the requested Passport does not exist."""


def transition_passport_lifecycle(
    db: Session,
    passport_id: int,
    new_state: str | PassportLifecycleState,
) -> AssetPassport:
    """
    Controlled lifecycle transition for a SAL Asset Passport.

    This service is the single place responsible for changing
    passport.lifecycle_state.
    """

    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.id == passport_id)
        .first()
    )

    if not passport:
        raise PassportNotFoundError(
            f"Asset Passport {passport_id} was not found"
        )

    try:
        current_state = PassportLifecycleState(
            passport.lifecycle_state
        )
    except ValueError as exc:
        raise PassportLifecycleTransitionError(
            f"Passport {passport.id} has an invalid current lifecycle state: "
            f"{passport.lifecycle_state}"
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

    passport.lifecycle_state = requested_state.value

    db.flush()

    return passport
