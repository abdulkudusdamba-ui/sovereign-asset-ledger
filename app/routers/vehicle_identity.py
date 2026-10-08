from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.schemas.vehicle_identity import VehicleIdentityResponse
from app.services.vehicle_identity_service import (
    VehicleIdentityConflictError,
    VehicleIdentityNotFoundError,
    get_vehicle_identity_by_sal_id,
)


router = APIRouter(
    prefix="/vehicle-identity",
    tags=["Vehicle Identity"],
)


@router.get(
    "/{sal_id}",
    response_model=VehicleIdentityResponse,
)
def get_vehicle_identity(
    sal_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(["admin", "registrar", "government"])
    ),
):
    try:
        return get_vehicle_identity_by_sal_id(
            db,
            sal_id=sal_id,
        )

    except VehicleIdentityNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except VehicleIdentityConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
