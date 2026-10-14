import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums.asset_types import AssetType
from app.models.asset import Asset
from app.models.asset_registry import AssetRegistry
from app.models.diamond import Diamond
from app.models.gold import Gold
from app.models.land import Land
from app.models.offline_sync import OfflineSyncConflict, OfflineSyncOperation
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.offline_sync import OfflineOperationInput
from app.services.asset_service import create_asset_registry_record
from app.services.audit_service import record_audit_event


MAX_BATCH_SIZE = 100
ASSET_MODELS = {
    "asset": (Asset, AssetType.OTHER),
    "land": (Land, AssetType.LAND),
    "vehicle": (Vehicle, AssetType.VEHICLE),
    "gold": (Gold, AssetType.GOLD),
    "diamond": (Diamond, AssetType.DIAMOND),
}
ASSET_SCHEMAS: dict[str, type[BaseModel]] = {}
CREATE_ROLES = {"admin", "registrar"}


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class GenericAssetPayload(StrictPayload):
    owner: str = Field(min_length=1, max_length=200)
    asset_name: str = Field(min_length=1, max_length=200)
    value: float = Field(ge=0, allow_inf_nan=False)


class LandPayload(StrictPayload):
    parcel_number: str = Field(min_length=1, max_length=200)
    owner_name: str = Field(min_length=1, max_length=200)
    community: str = Field(min_length=1, max_length=200)
    district: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=200)
    size: float = Field(gt=0, allow_inf_nan=False)
    land_use: str = Field(min_length=1, max_length=200)
    estimated_value: float = Field(ge=0, allow_inf_nan=False)


class VehiclePayload(StrictPayload):
    owner: str = Field(min_length=1, max_length=200)
    registration_number: str = Field(min_length=1, max_length=200)
    vin: str = Field(min_length=1, max_length=200)
    manufacturer: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    year: int = Field(ge=1886, le=2200)
    engine_number: str = Field(min_length=1, max_length=200)
    color: str = Field(min_length=1, max_length=100)
    estimated_value: float = Field(ge=0, allow_inf_nan=False)
    chassis_number: str | None = Field(default=None, max_length=200)


class GoldPayload(StrictPayload):
    owner: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=100)
    purity: str = Field(min_length=1, max_length=100)
    weight: float = Field(gt=0, allow_inf_nan=False)
    estimated_value: float = Field(ge=0, allow_inf_nan=False)
    serial_number: str = Field(min_length=1, max_length=200)


class DiamondPayload(StrictPayload):
    owner: str = Field(min_length=1, max_length=200)
    gemstone: str = Field(min_length=1, max_length=100)
    carat: float = Field(gt=0, allow_inf_nan=False)
    cut: str = Field(min_length=1, max_length=100)
    color: str = Field(min_length=1, max_length=100)
    clarity: str = Field(min_length=1, max_length=100)
    certificate_number: str = Field(min_length=1, max_length=200)
    estimated_value: float = Field(ge=0, allow_inf_nan=False)


ASSET_SCHEMAS.update(
    asset=GenericAssetPayload,
    land=LandPayload,
    vehicle=VehiclePayload,
    gold=GoldPayload,
    diamond=DiamondPayload,
)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _result(
    operation_id: str | None,
    asset_type: str | None,
    status: str,
    message: str,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "operation_id": operation_id,
        "asset_type": asset_type,
        "status": status,
        "record_id": None,
        "sal_id": None,
        "conflict_id": None,
        "message": message,
        **fields,
    }


def _audit(
    db: Session,
    *,
    user: User,
    action: str,
    operation_id: str,
    result: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    record_audit_event(
        db,
        actor_id=user.id,
        actor_type="user",
        action=action,
        entity_type="offline_sync_operation",
        entity_id=operation_id,
        source="offline_sync",
        reason=reason,
        reference=operation_id,
        result=result,
        metadata=metadata or {},
    )


def _record_operation(
    db: Session,
    *,
    user: User,
    operation_id: str,
    asset_type: str,
    request_hash: str,
    payload: dict[str, Any],
    result: dict[str, Any],
) -> OfflineSyncOperation:
    row = OfflineSyncOperation(
        actor_id=user.id,
        operation_id=operation_id,
        asset_type=asset_type,
        request_hash=request_hash,
        request_payload=_json(payload),
        status=result["status"],
        result_payload=_json(result),
    )
    db.add(row)
    db.flush()
    return row


def _set_result(row: OfflineSyncOperation, result: dict[str, Any]) -> None:
    row.status = result["status"]
    row.result_payload = _json(result)


def _find_duplicate(db: Session, asset_type: str, data: dict[str, Any]):
    model = ASSET_MODELS[asset_type][0]
    fields = {
        "land": ("parcel_number",),
        "vehicle": ("vin", "registration_number"),
        "gold": ("serial_number",),
        "diamond": ("certificate_number",),
    }.get(asset_type, ())
    for field in fields:
        value = data.get(field)
        if value is not None:
            existing = db.query(model).filter(getattr(model, field) == value).first()
            if existing is not None:
                return field, value, existing
    return None


def _create_conflict(
    db: Session,
    *,
    user: User,
    operation: OfflineSyncOperation,
    operation_id: str,
    asset_type: str,
    request_hash: str,
    payload: dict[str, Any],
    conflict_type: str,
    result: dict[str, Any],
    identifier_type: str | None = None,
    identifier_value: str | None = None,
) -> dict[str, Any]:
    conflict = (
        db.query(OfflineSyncConflict)
        .filter(
            OfflineSyncConflict.operation_record_id == operation.id,
            OfflineSyncConflict.submission_hash == request_hash,
        )
        .first()
    )
    if conflict is None:
        conflict = OfflineSyncConflict(
            operation_record_id=operation.id,
            submission_hash=request_hash,
            conflict_type=conflict_type,
            asset_type=asset_type,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            submitted_payload=_json(payload),
        )
        db.add(conflict)
        db.flush()
    result["conflict_id"] = conflict.id
    _set_result(operation, result)
    _audit(
        db,
        user=user,
        action="offline.conflict_detected",
        operation_id=operation_id,
        result="conflict",
        reason="Offline submission requires authorized review",
        metadata={"conflict_id": conflict.id, "conflict_type": conflict_type},
    )
    db.commit()
    return result


def _persist_invalid_operation(
    db: Session,
    *,
    user: User,
    operation_id: str,
    asset_type: str,
    request_hash: str,
    payload: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    result = _result(operation_id, asset_type, "rejected", message)
    try:
        operation = _record_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=payload,
            result=result,
        )
        _audit(
            db,
            user=user,
            action="offline.operation_rejected",
            operation_id=operation_id,
            result="rejected",
            reason="Offline operation failed validation or authorization",
            metadata={"asset_type": asset_type},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(OfflineSyncOperation)
            .filter_by(actor_id=user.id, operation_id=operation_id)
            .first()
        )
        if existing and existing.request_hash == request_hash:
            _audit(
                db,
                user=user,
                action="offline.duplicate_submission",
                operation_id=operation_id,
                result="duplicate_submission",
                reason="Repeated offline operation",
            )
            db.commit()
            return json.loads(existing.result_payload)
        if existing:
            return _create_conflict(
                db,
                user=user,
                operation=existing,
                operation_id=operation_id,
                asset_type=asset_type,
                request_hash=request_hash,
                payload=payload,
                conflict_type="IDEMPOTENCY_KEY_REUSE",
                result=_result(
                    operation_id,
                    asset_type,
                    "conflict",
                    "Operation identifier was already used for different data",
                ),
            )
        raise
    return result


def _process_operation(db: Session, user: User, raw: dict[str, Any]) -> dict[str, Any]:
    raw_operation_id = raw.get("operation_id")
    try:
        operation_id = str(UUID(raw_operation_id))
    except (ValueError, TypeError, AttributeError):
        reference = str(uuid4())
        _audit(
            db,
            user=user,
            action="offline.operation_rejected",
            operation_id=reference,
            result="rejected",
            reason="Offline operation identifier was invalid",
            metadata={"validation_error": "invalid_operation_id"},
        )
        db.commit()
        return _result(
            None,
            raw.get("asset_type") if isinstance(raw.get("asset_type"), str) else None,
            "rejected",
            "A valid UUID operation_id is required",
        )

    request_hash = _hash(raw)
    raw_asset_type = raw.get("asset_type")
    asset_type = (
        raw_asset_type.strip().lower()
        if isinstance(raw_asset_type, str)
        else "unknown"
    )[:50] or "unknown"
    existing = (
        db.query(OfflineSyncOperation)
        .filter_by(actor_id=user.id, operation_id=operation_id)
        .first()
    )
    if existing is not None:
        if existing.request_hash == request_hash:
            _audit(
                db,
                user=user,
                action="offline.duplicate_submission",
                operation_id=operation_id,
                result="duplicate_submission",
                reason="Repeated offline operation",
                metadata={"asset_type": existing.asset_type},
            )
            db.commit()
            return json.loads(existing.result_payload)
        return _create_conflict(
            db,
            user=user,
            operation=existing,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            conflict_type="IDEMPOTENCY_KEY_REUSE",
            result=_result(
                operation_id,
                asset_type,
                "conflict",
                "Operation identifier was already used for different data",
            ),
        )

    try:
        operation_input = OfflineOperationInput.model_validate(raw)
        UUID(operation_input.operation_id)
    except (ValidationError, ValueError, TypeError):
        return _persist_invalid_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            message="Operation request failed schema validation",
        )

    asset_type = operation_input.asset_type.strip().lower()
    if operation_input.operation != "create":
        return _persist_invalid_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            message="Only create operations are supported",
        )
    if asset_type not in ASSET_MODELS:
        return _persist_invalid_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            message="Asset type is not supported for offline creation",
        )
    try:
        payload = ASSET_SCHEMAS[asset_type].model_validate(operation_input.data)
    except ValidationError:
        return _persist_invalid_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            message="Asset data failed schema validation",
        )
    data = payload.model_dump()

    if user.role not in CREATE_ROLES:
        return _persist_invalid_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            message="User is not authorized to create this asset type",
        )

    duplicate = _find_duplicate(db, asset_type, data)
    if duplicate is not None:
        identifier_type, identifier_value, _ = duplicate
        result = _result(
            operation_id,
            asset_type,
            "conflict",
            "A matching unique identifier already exists",
        )
        operation = _record_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            result=result,
        )
        return _create_conflict(
            db,
            user=user,
            operation=operation,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            conflict_type="DUPLICATE_IDENTIFIER",
            identifier_type=identifier_type,
            identifier_value=str(identifier_value)[:200],
            result=result,
        )

    model, registry_type = ASSET_MODELS[asset_type]
    record = model(**data)
    if asset_type in {"vehicle", "gold", "diamond"}:
        record.status = "PENDING_REVIEW"
    try:
        db.add(record)
        db.flush()
        owner = data.get("owner", data.get("owner_name"))
        estimated_value = data.get("estimated_value", data.get("value", 0))
        registry = create_asset_registry_record(
            db=db,
            asset_type=registry_type,
            registry_id=record.id,
            owner=owner,
            estimated_value=estimated_value,
            status="PENDING_REVIEW",
            sal_verification="PENDING",
        )
        db.flush()
        result = _result(
            operation_id,
            asset_type,
            "created",
            "Asset submission recorded; ownership and verification remain pending",
            record_id=record.id,
            sal_id=registry.sal_id,
        )
        _record_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            result=result,
        )
        _audit(
            db,
            user=user,
            action="offline.asset_created",
            operation_id=operation_id,
            result="created",
            reason="Offline asset creation recorded pending review",
            metadata={
                "asset_type": asset_type,
                "record_id": record.id,
                "asset_registry_id": registry.id,
            },
        )
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(OfflineSyncOperation)
            .filter_by(actor_id=user.id, operation_id=operation_id)
            .first()
        )
        if existing is not None:
            if existing.request_hash == request_hash:
                _audit(
                    db,
                    user=user,
                    action="offline.duplicate_submission",
                    operation_id=operation_id,
                    result="duplicate_submission",
                    reason="Repeated concurrent offline operation",
                )
                db.commit()
                return json.loads(existing.result_payload)
            return _create_conflict(
                db,
                user=user,
                operation=existing,
                operation_id=operation_id,
                asset_type=asset_type,
                request_hash=request_hash,
                payload=raw,
                conflict_type="IDEMPOTENCY_KEY_REUSE",
                result=_result(
                    operation_id,
                    asset_type,
                    "conflict",
                    "Operation identifier was already used for different data",
                ),
            )
        duplicate = _find_duplicate(db, asset_type, data)
        if duplicate is not None:
            identifier_type, identifier_value, _ = duplicate
            result = _result(
                operation_id,
                asset_type,
                "conflict",
                "A matching unique identifier already exists",
            )
            operation = _record_operation(
                db,
                user=user,
                operation_id=operation_id,
                asset_type=asset_type,
                request_hash=request_hash,
                payload=raw,
                result=result,
            )
            return _create_conflict(
                db,
                user=user,
                operation=operation,
                operation_id=operation_id,
                asset_type=asset_type,
                request_hash=request_hash,
                payload=raw,
                conflict_type="DUPLICATE_IDENTIFIER",
                identifier_type=identifier_type,
                identifier_value=str(identifier_value)[:200],
                result=result,
            )
        return _persist_invalid_operation(
            db,
            user=user,
            operation_id=operation_id,
            asset_type=asset_type,
            request_hash=request_hash,
            payload=raw,
            message="Asset could not be created because a database constraint was violated",
        )


def process_batch(db: Session, user: User, operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_process_operation(db, user, operation) for operation in operations]


def list_conflicts(
    db: Session,
    *,
    user: User,
    limit: int,
    offset: int,
) -> list[tuple[OfflineSyncConflict, str]]:
    query = (
        db.query(OfflineSyncConflict, OfflineSyncOperation.operation_id)
        .join(
            OfflineSyncOperation,
            OfflineSyncOperation.id == OfflineSyncConflict.operation_record_id,
        )
        .order_by(OfflineSyncConflict.created_at.desc(), OfflineSyncConflict.id.desc())
    )
    if user.role != "admin":
        query = query.filter(OfflineSyncOperation.actor_id == user.id)
    return query.offset(offset).limit(limit).all()


def resolve_conflict(
    db: Session,
    *,
    user: User,
    conflict_id: int,
    resolution: str,
) -> OfflineSyncConflict | None:
    conflict = (
        db.query(OfflineSyncConflict)
        .filter(OfflineSyncConflict.id == conflict_id)
        .first()
    )
    if conflict is None or conflict.status != "OPEN":
        return None
    conflict.status = "RESOLVED"
    conflict.resolution = resolution
    conflict.resolved_by = user.id
    conflict.resolved_at = datetime.now(timezone.utc)
    operation = (
        db.query(OfflineSyncOperation)
        .filter(OfflineSyncOperation.id == conflict.operation_record_id)
        .first()
    )
    if operation is not None:
        result = json.loads(operation.result_payload)
        result["status"] = "resolved"
        result["message"] = "Conflict was reviewed; no asset was changed"
        result["resolution"] = resolution
        _set_result(operation, result)
        _audit(
            db,
            user=user,
            action="offline.conflict_resolved",
            operation_id=operation.operation_id,
            result="resolved",
            reason="Offline conflict resolved by an authorized reviewer",
            metadata={"conflict_id": conflict.id, "resolution": resolution},
        )
    db.commit()
    db.refresh(conflict)
    return conflict


def conflict_submission(conflict: OfflineSyncConflict) -> dict[str, Any]:
    return json.loads(conflict.submitted_payload)
