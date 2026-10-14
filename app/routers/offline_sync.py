from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.database.database import get_db
from app.models.offline_sync import OfflineSyncConflict, OfflineSyncOperation
from app.models.user import User
from app.schemas.offline_sync import (
    OfflineConflictResolution,
    OfflineConflictResponse,
    OfflineSyncBatch,
    OfflineSyncResponse,
)
from app.services.offline_sync_service import (
    conflict_submission,
    list_conflicts,
    process_batch,
    resolve_conflict,
)


MAX_REQUEST_BYTES = 1_048_576


class OfflineSyncRequestLimitRoute(APIRoute):
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def limited_handler(request: Request):
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_REQUEST_BYTES:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": "Offline sync request is too large"},
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length"},
                    )

            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Offline sync request is too large"},
                    )
            request._body = bytes(body)
            return await original_handler(request)

        return limited_handler


router = APIRouter(
    prefix="/offline-sync",
    tags=["Offline Sync"],
    route_class=OfflineSyncRequestLimitRoute,
)


@router.post("/batches", response_model=OfflineSyncResponse)
def sync_batch(
    batch: OfflineSyncBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"results": process_batch(db, current_user, batch.operations)}


@router.get("/conflicts", response_model=list[OfflineConflictResponse])
def get_conflicts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = list_conflicts(db, user=current_user, limit=limit, offset=offset)
    return [
        {
            "id": conflict.id,
            "operation_id": operation_id,
            "asset_type": conflict.asset_type,
            "conflict_type": conflict.conflict_type,
            "identifier_type": conflict.identifier_type,
            "identifier_value": conflict.identifier_value,
            "submitted_payload": conflict_submission(conflict),
            "status": conflict.status,
            "resolution": conflict.resolution,
            "created_at": conflict.created_at.isoformat(),
        }
        for conflict, operation_id in rows
    ]


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=OfflineConflictResponse,
)
def resolve_offline_conflict(
    conflict_id: int,
    resolution: OfflineConflictResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    conflict = resolve_conflict(
        db,
        user=current_user,
        conflict_id=conflict_id,
        resolution=resolution.resolution,
    )
    if conflict is None:
        raise HTTPException(status_code=404, detail="Open conflict not found")
    operation_id = (
        db.query(OfflineSyncOperation.operation_id)
        .select_from(OfflineSyncConflict)
        .filter(OfflineSyncConflict.id == conflict.id)
        .join(
            OfflineSyncOperation,
            OfflineSyncOperation.id == OfflineSyncConflict.operation_record_id,
        )
        .scalar()
    )
    return {
        "id": conflict.id,
        "operation_id": operation_id,
        "asset_type": conflict.asset_type,
        "conflict_type": conflict.conflict_type,
        "identifier_type": conflict.identifier_type,
        "identifier_value": conflict.identifier_value,
        "submitted_payload": conflict_submission(conflict),
        "status": conflict.status,
        "resolution": conflict.resolution,
        "created_at": conflict.created_at.isoformat(),
    }
