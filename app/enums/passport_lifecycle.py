from enum import Enum


class PassportLifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    TRANSFERRED = "TRANSFERRED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


ALLOWED_PASSPORT_TRANSITIONS: dict[
    PassportLifecycleState,
    set[PassportLifecycleState],
] = {
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


def is_valid_passport_transition(
    current_state: PassportLifecycleState,
    new_state: PassportLifecycleState,
) -> bool:
    return new_state in ALLOWED_PASSPORT_TRANSITIONS.get(
        current_state,
        set(),
    )
