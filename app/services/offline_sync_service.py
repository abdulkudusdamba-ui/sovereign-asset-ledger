import hashlib
import json
import math
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset_external_identifier import AssetExternalIdentifier
from app.models.asset_registry import AssetRegistry
from app.models.land import Land
from app.models.offline_sync import OfflineSyncConflict, OfflineSyncOperation
from app.models.vehicle import Vehicle
from app.schemas.offline_sync import OfflineSyncOperationRequest
from app.services.audit_service import record_audit_event
from app.services.asset_external_identifier_service import add_external_identifier


class OfflineSyncError(Exception):
    pass


class OfflineSyncNotFoundError(OfflineSyncError):
    pass


class OfflineSyncConflictStateError(OfflineSyncError):
    pass


def _serialize(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _new_conflict(
    db: Session,
    *,
    operation_id: str,
    submitted_by: int,
    payload: str,
    reason: str,
    operation_record_id: int | None,
) -> OfflineSyncConflict:
    conflict = OfflineSyncConflict(
        operation_record_id=operation_record_id,
        operation_id=operation_id,
        submitted_by=submitted_by,
        submission_payload=payload,
        reason=reason,
        status="PENDING",
    )
    db.add(conflict)
    db.flush()
    return conflict


def _result(
    operation_id: str,
    outcome: str,
    record_status: str,
    message: str,
    conflict_id: int | None = None,
) -> dict:
    return {
        "operation_id": operation_id,
        "outcome": outcome,
        "record_status": record_status,
        "conflict_id": conflict_id,
        "message": message,
    }


def _validate_changes(changes: dict) -> tuple[dict | None, str | None]:
    allowed = {"owner", "status", "estimated_value", "identifier"}
    if not changes or set(changes) - allowed:
        return None, "Changes contain unsupported or no fields"

    normalized = {}
    if "owner" in changes:
        owner = changes["owner"]
        if not isinstance(owner, str) or not owner.strip() or len(owner.strip()) > 256:
            return None, "Owner must contain 1 to 256 characters"
        normalized["owner"] = owner.strip()

    if "status" in changes:
        status = changes["status"]
        if not isinstance(status, str) or not status.strip():
            return None, "Status must be a non-empty string"
        if len(status) > 64:
            return None, "Status must be at most 64 characters"
        normalized["status"] = status.strip()

    if "estimated_value" in changes:
        value = changes["estimated_value"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            return None, "Estimated value must be a finite non-negative number"
        normalized["estimated_value"] = float(value)

    if "identifier" in changes:
        identifier = changes["identifier"]
        if not isinstance(identifier, dict) or set(identifier) != {"type", "value"}:
            return None, "Identifier must contain only type and value"
        identifier_type = identifier["type"]
        identifier_value = identifier["value"]
        if not isinstance(identifier_type, str) or not isinstance(identifier_value, str):
            return None, "Identifier type and value must be strings"
        identifier_type = identifier_type.strip().upper()
        identifier_value = identifier_value.strip().upper()
        if identifier_type not in {"VIN", "PARCEL_NUMBER"}:
            return None, "Identifier type must be VIN or PARCEL_NUMBER"
        if not identifier_value or len(identifier_value) > 128:
            return None, "Identifier value must contain 1 to 128 characters"
        normalized["identifier"] = {
            "type": identifier_type,
            "value": identifier_value,
        }

    return normalized, None


def _duplicate_identifier_asset(
    db: Session,
    *,
    identifier_type: str,
    identifier_value: str,
) -> int | None:
    external = (
        db.query(AssetExternalIdentifier)
        .filter(
            AssetExternalIdentifier.identifier_type == identifier_type,
            func.upper(AssetExternalIdentifier.identifier_value) == identifier_value,
            AssetExternalIdentifier.status == "ACTIVE",
        )
        .first()
    )
    if external is not None:
        return external.asset_registry_id

    if identifier_type == "VIN":
        identity = (
            db.query(Vehicle)
            .filter(func.upper(Vehicle.vin) == identifier_value)
            .first()
        )
        asset_type = "Vehicle"
    else:
        identity = (
            db.query(Land)
            .filter(func.upper(Land.parcel_number) == identifier_value)
            .first()
        )
        asset_type = "Land"

    if identity is None:
        return None

    asset = (
        db.query(AssetRegistry)
        .filter(
            AssetRegistry.asset_type == asset_type,
            AssetRegistry.registry_id == identity.id,
        )
        .first()
    )
    return asset.id if asset is not None else -1


def _record_asset_update(
    db: Session,
    *,
    operation: OfflineSyncOperation,
    actor_id: int,
    asset: AssetRegistry,
    changes: dict,
) -> None:
    if "identifier" in changes:
        expected_asset_type = {
            "VIN": "Vehicle",
            "PARCEL_NUMBER": "Land",
        }[changes["identifier"]["type"]]
        if asset.asset_type != expected_asset_type:
            raise OfflineSyncConflictStateError(
                f"{changes['identifier']['type']} identifiers require a "
                f"{expected_asset_type} asset"
            )

    before_version = asset.version
    changed_fields = []

    if "owner" in changes and changes["owner"] != asset.owner:
        asset.owner = changes["owner"]
        changed_fields.append("owner")
    if "status" in changes and changes["status"] != asset.status:
        asset.status = changes["status"]
        changed_fields.append("status")
    if (
        "estimated_value" in changes
        and changes["estimated_value"] != asset.estimated_value
    ):
        asset.estimated_value = changes["estimated_value"]
        changed_fields.append("estimated_value")

    if "identifier" in changes:
        identifier = changes["identifier"]
        existing_on_asset = (
            db.query(AssetExternalIdentifier)
            .filter(
                AssetExternalIdentifier.asset_registry_id == asset.id,
                AssetExternalIdentifier.identifier_type == identifier["type"],
                func.upper(AssetExternalIdentifier.identifier_value)
                == identifier["value"],
                AssetExternalIdentifier.status == "ACTIVE",
            )
            .first()
        )
        if existing_on_asset is None:
            add_external_identifier(
                db,
                asset_registry_id=asset.id,
                authority="SAL",
                identifier_type=identifier["type"],
                identifier_value=identifier["value"],
                source_reference=operation.operation_id,
                actor_id=actor_id,
                actor_type="USER",
                source="OFFLINE_SYNC",
                reason="Accepted offline synchronization operation",
                reference=operation.operation_id,
            )
            changed_fields.append("identifier")

    if not changed_fields:
        raise OfflineSyncConflictStateError("The submitted operation makes no changes")

    asset.version = before_version + 1
    db.flush()
    record_audit_event(
        db,
        actor_id=actor_id,
        actor_type="USER",
        action="OFFLINE_SYNC_OPERATION_ACCEPTED",
        entity_type="OFFLINE_SYNC_OPERATION",
        entity_id=operation.id,
        asset_registry_id=asset.id,
        source="OFFLINE_SYNC",
        reference=operation.operation_id,
        result="SUCCESS",
        before_data={"asset_version": before_version},
        after_data={
            "asset_version": asset.version,
            "asset_registry_id": asset.id,
            "changed_fields": changed_fields,
        },
    )
    operation.asset_registry_id = asset.id
    operation.status = "ACCEPTED"


def synchronize_batch(db: Session, *, actor_id: int, operations: list) -> list[dict]:
    results = []

    for item in operations:
        payload_data = item.model_dump(mode="json")
        payload = _serialize(payload_data)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        operation_id = str(item.operation_id)
        existing = (
            db.query(OfflineSyncOperation)
            .filter(OfflineSyncOperation.operation_id == operation_id)
            .first()
        )

        if existing is not None:
            if existing.actor_id == actor_id and existing.payload_hash == payload_hash:
                results.append(
                    _result(
                        operation_id,
                        "DUPLICATE",
                        existing.status,
                        "Operation was already received; no changes were applied",
                    )
                )
            else:
                conflict = _new_conflict(
                    db,
                    operation_id=operation_id,
                    submitted_by=actor_id,
                    payload=payload,
                    reason="OPERATION_ID_REUSE",
                    operation_record_id=existing.id,
                )
                results.append(
                    _result(
                        operation_id,
                        "CONFLICT",
                        existing.status,
                        "Operation ID is already associated with a different submission",
                        conflict.id,
                    )
                )
            continue

        operation = OfflineSyncOperation(
            operation_id=operation_id,
            actor_id=actor_id,
            payload=payload,
            payload_hash=payload_hash,
            status="RECEIVED",
        )
        try:
            with db.begin_nested():
                db.add(operation)
                db.flush()
        except IntegrityError:
            existing = (
                db.query(OfflineSyncOperation)
                .filter(OfflineSyncOperation.operation_id == operation_id)
                .first()
            )
            if existing is None:
                raise
            if existing.actor_id == actor_id and existing.payload_hash == payload_hash:
                results.append(
                    _result(
                        operation_id,
                        "DUPLICATE",
                        existing.status,
                        "Operation was already received; no changes were applied",
                    )
                )
            else:
                conflict = _new_conflict(
                    db,
                    operation_id=operation_id,
                    submitted_by=actor_id,
                    payload=payload,
                    reason="OPERATION_ID_REUSE",
                    operation_record_id=existing.id,
                )
                results.append(
                    _result(
                        operation_id,
                        "CONFLICT",
                        existing.status,
                        "Operation ID is already associated with a different submission",
                        conflict.id,
                    )
                )
            continue

        changes, error = _validate_changes(item.changes)
        if error is not None:
            operation.status = "REJECTED"
            results.append(
                _result(operation_id, "REJECTED", operation.status, error)
            )
            continue

        asset = (
            db.query(AssetRegistry)
            .filter(AssetRegistry.id == item.asset_registry_id)
            .first()
        )
        if asset is None:
            operation.status = "REJECTED"
            results.append(
                _result(
                    operation_id,
                    "REJECTED",
                    operation.status,
                    "Asset registry record was not found",
                )
            )
            continue

        operation.asset_registry_id = asset.id
        reason = None
        if "identifier" in changes:
            expected_asset_type = {
                "VIN": "Vehicle",
                "PARCEL_NUMBER": "Land",
            }[changes["identifier"]["type"]]
            if asset.asset_type != expected_asset_type:
                operation.status = "REJECTED"
                results.append(
                    _result(
                        operation_id,
                        "REJECTED",
                        operation.status,
                        f"{changes['identifier']['type']} identifiers require a "
                        f"{expected_asset_type} asset",
                    )
                )
                continue
        if changes.get("owner") is not None and changes["owner"] != asset.owner:
            reason = "OWNERSHIP_REVIEW"
        elif item.expected_version != asset.version:
            reason = "CONCURRENT_UPDATE"
        elif "identifier" in changes:
            duplicate_asset_id = _duplicate_identifier_asset(
                db,
                identifier_type=changes["identifier"]["type"],
                identifier_value=changes["identifier"]["value"],
            )
            if duplicate_asset_id is not None and duplicate_asset_id != asset.id:
                reason = "DUPLICATE_IDENTIFIER"

        if reason is not None:
            operation.status = "CONFLICT"
            conflict = _new_conflict(
                db,
                operation_id=operation_id,
                submitted_by=actor_id,
                payload=payload,
                reason=reason,
                operation_record_id=operation.id,
            )
            results.append(
                _result(
                    operation_id,
                    "CONFLICT",
                    operation.status,
                    "Submission requires authorized human review",
                    conflict.id,
                )
            )
            continue

        try:
            _record_asset_update(
                db,
                operation=operation,
                actor_id=actor_id,
                asset=asset,
                changes=changes,
            )
        except OfflineSyncConflictStateError:
            operation.status = "REJECTED"
            results.append(
                _result(
                    operation_id,
                    "REJECTED",
                    operation.status,
                    "Changes could not be applied",
                )
            )
            continue

        results.append(
            _result(
                operation_id,
                "ACCEPTED",
                operation.status,
                "Operation was accepted and applied",
            )
        )

    return results


def resolve_conflict(
    db: Session,
    *,
    conflict_id: int,
    reviewer_id: int,
    resolution: str,
    note: str,
) -> OfflineSyncConflict:
    conflict = (
        db.query(OfflineSyncConflict)
        .filter(OfflineSyncConflict.id == conflict_id)
        .first()
    )
    if conflict is None:
        raise OfflineSyncNotFoundError("Offline synchronization conflict was not found")
    if conflict.status != "PENDING":
        raise OfflineSyncConflictStateError("Conflict has already been resolved")

    operation = None
    if conflict.operation_record_id is not None:
        operation = (
            db.query(OfflineSyncOperation)
            .filter(OfflineSyncOperation.id == conflict.operation_record_id)
            .first()
        )

    if resolution == "ACCEPT":
        if conflict.reason == "OPERATION_ID_REUSE" or operation is None:
            raise OfflineSyncConflictStateError(
                "A reused operation ID cannot be accepted as a new operation"
            )
        item = OfflineSyncOperationRequest.model_validate_json(operation.payload)
        changes, error = _validate_changes(item.changes)
        if error is not None:
            raise OfflineSyncConflictStateError(error)
        asset = (
            db.query(AssetRegistry)
            .filter(AssetRegistry.id == item.asset_registry_id)
            .first()
        )
        if asset is None:
            raise OfflineSyncConflictStateError(
                "Asset registry record no longer exists"
            )
        if "identifier" in changes:
            duplicate_asset_id = _duplicate_identifier_asset(
                db,
                identifier_type=changes["identifier"]["type"],
                identifier_value=changes["identifier"]["value"],
            )
            if duplicate_asset_id is not None and duplicate_asset_id != asset.id:
                raise OfflineSyncConflictStateError(
                    "Duplicate identifier still exists and must be resolved first"
                )
        try:
            _record_asset_update(
                db,
                operation=operation,
                actor_id=reviewer_id,
                asset=asset,
                changes=changes,
            )
        except OfflineSyncConflictStateError as exc:
            raise OfflineSyncConflictStateError(str(exc)) from exc
        operation.status = "ACCEPTED"
    elif operation is not None and conflict.reason != "OPERATION_ID_REUSE":
        operation.status = "REJECTED"

    conflict.status = "RESOLVED"
    conflict.resolution = resolution
    conflict.resolution_note = note.strip()
    conflict.resolved_by = reviewer_id
    conflict.resolved_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db,
        actor_id=reviewer_id,
        actor_type="USER",
        action="OFFLINE_SYNC_CONFLICT_RESOLVED",
        entity_type="OFFLINE_SYNC_CONFLICT",
        entity_id=conflict.id,
        asset_registry_id=operation.asset_registry_id if operation else None,
        source="OFFLINE_SYNC_REVIEW",
        reference=conflict.operation_id,
        reason=note.strip(),
        result="SUCCESS",
        before_data={"status": "PENDING"},
        after_data={
            "status": conflict.status,
            "resolution": resolution,
            "reason": conflict.reason,
        },
    )
    return conflict
