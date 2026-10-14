from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.database.database import get_db
from app.models.user import User
from app.schemas.offline_sync import (
    OfflineSyncBatchRequest,
    OfflineSyncBatchResponse,
    OfflineSyncConflictResolution,
    OfflineSyncConflictResponse,
)
from app.services.offline_sync_service import (
    OfflineSyncConflictStateError,
    OfflineSyncNotFoundError,
    resolve_conflict,
    synchronize_batch,
)


router = APIRouter(prefix="/offline-sync", tags=["Offline SAL Synchronization"])
SYNC_ROLES = ["admin", "registrar"]


@router.post(
    "/batches",
    response_model=OfflineSyncBatchResponse,
)
def sync_batch(
    request: OfflineSyncBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(SYNC_ROLES)),
):
    results = synchronize_batch(
        db,
        actor_id=current_user.id,
        operations=request.operations,
    )
    db.commit()
    return {"results": results}


@router.post(
    "/conflicts/{conflict_id}/resolution",
    response_model=OfflineSyncConflictResponse,
)
def resolve_sync_conflict(
    conflict_id: int,
    request: OfflineSyncConflictResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(SYNC_ROLES)),
):
    try:
        conflict = resolve_conflict(
            db,
            conflict_id=conflict_id,
            reviewer_id=current_user.id,
            resolution=request.resolution,
            note=request.note,
        )
        db.commit()
        db.refresh(conflict)
        return conflict
    except OfflineSyncNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OfflineSyncConflictStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
