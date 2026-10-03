from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.core.auth import require_role
from app.models.asset_passport import AssetPassport
from app.models.asset_registry import AssetRegistry
from app.models.passport_lifecycle_history import PassportLifecycleHistory
from app.services.passport_lifecycle_service import (
    PassportConcurrencyError,
    PassportLifecycleTransitionError,
    PassportNotFoundError,
    get_passport_lifecycle_semantics,
    transition_passport_lifecycle,
)
from app.schemas.asset_passport import (
    AssetPassportCreate,
    AssetPassportResponse,
)

router = APIRouter(prefix="/passport", tags=["Asset Passport"])


class PassportLifecycleUpdate(BaseModel):
    lifecycle_state: str
    expected_version: int
    reason: str | None = None
    reference: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("lifecycle_state")
    @classmethod
    def validate_lifecycle_state(cls, value: str) -> str:
        allowed_states = {
            "REGISTERED",
            "ACTIVE",
            "TRANSFER_PENDING",
            "TRANSFERRED",
            "SUSPENDED",
            "RETIRED",
        }

        if value not in allowed_states:
            raise ValueError(
                f"Invalid Passport lifecycle state: {value}"
            )

        return value

    @field_validator("expected_version")
    @classmethod
    def validate_expected_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError(
                "expected_version must be greater than or equal to 1"
            )

        return value


class PassportLifecycleHistoryResponse(BaseModel):
    id: int
    passport_id: int
    from_state: str
    to_state: str
    reason: str | None = None
    reference: str | None = None
    changed_by: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def build_passport_response(
    passport: AssetPassport,
    asset: AssetRegistry,
) -> AssetPassportResponse:
    return AssetPassportResponse(
        id=passport.id,
        passport_id=passport.passport_id,
        asset_registry_id=passport.asset_registry_id,
        sal_id=asset.sal_id,
        asset_type=asset.asset_type,
        owner=asset.owner,
        estimated_value=asset.estimated_value,
        asset_status=asset.status,
        status=passport.status,
        lifecycle_state=passport.lifecycle_state,
        version=passport.version,
        created_at=passport.created_at,
        updated_at=passport.updated_at,
    )


@router.post(
    "/{sal_id}",
    response_model=AssetPassportResponse,
    status_code=201,
)
@router.get(
    "/lifecycle-states",
)
def get_passport_lifecycle_states():
    """Return the controlled operational semantics for Passport lifecycle states."""
    return get_passport_lifecycle_semantics()


def create_passport(
    sal_id: str,
    payload: AssetPassportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="SAL asset identity not found",
        )

    existing = (
        db.query(AssetPassport)
        .filter(AssetPassport.asset_registry_id == asset.id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Asset Passport already exists for this SAL asset",
        )

    passport = AssetPassport(
        passport_id=f"SAL-PASSPORT-{__import__('secrets').token_hex(6).upper()}",
        asset_registry_id=asset.id,
        status="ACTIVE",
        lifecycle_state="REGISTERED",
    )

    db.add(passport)
    db.commit()
    db.refresh(passport)

    return build_passport_response(passport, asset)


@router.get(
    "/{sal_id}",
    response_model=AssetPassportResponse,
)
def get_passport(
    sal_id: str,
    db: Session = Depends(get_db),
):
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="SAL asset identity not found",
        )

    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.asset_registry_id == asset.id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found",
        )

    return build_passport_response(passport, asset)


@router.get(
    "/{passport_id}/history",
    response_model=list[PassportLifecycleHistoryResponse],
)
def get_passport_history(
    passport_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar", "government"])),
):
    passport = (
        db.query(AssetPassport)
        .filter(AssetPassport.id == passport_id)
        .first()
    )

    if not passport:
        raise HTTPException(
            status_code=404,
            detail="Asset Passport not found",
        )

    history = (
        db.query(PassportLifecycleHistory)
        .filter(PassportLifecycleHistory.passport_id == passport_id)
        .order_by(
            PassportLifecycleHistory.created_at.asc(),
            PassportLifecycleHistory.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return history


@router.patch(
    "/{passport_id}/lifecycle",
    response_model=AssetPassportResponse,
)
def update_passport_lifecycle(
    passport_id: int,
    payload: PassportLifecycleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "registrar"])),
):
    try:
        passport = transition_passport_lifecycle(
            db=db,
            passport_id=passport_id,
            new_state=payload.lifecycle_state,
            expected_version=payload.expected_version,
            reason=payload.reason,
            reference=payload.reference,
            changed_by=current_user.email,
        )

        db.commit()
        db.refresh(passport)

    except PassportNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PassportLifecycleTransitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except PassportConcurrencyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Passport was modified by another transaction; "
                "retry with the current Passport state"
            ),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        error_text = str(exc.orig).lower()

        if (
            "passport_lifecycle_history.reference" in error_text
            or "uq_passport_lifecycle_history_reference" in error_text
        ):
            raise HTTPException(
                status_code=409,
                detail="Lifecycle reference already exists",
            ) from exc

        raise HTTPException(
            status_code=409,
            detail="Lifecycle operation violates a database integrity constraint",
        ) from exc

    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.id == passport.asset_registry_id)
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=409,
            detail="Passport exists, but linked SAL asset identity was not found",
        )

    return build_passport_response(passport, asset)
