import json
import uuid

from app.core.security import hash_password
from app.models.asset_external_identifier import AssetExternalIdentifier
from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.models.offline_sync import OfflineSyncConflict, OfflineSyncOperation
from app.models.user import User


PASSWORD = "SAL-offline-test-password"


def _login(client, test_db, *, role, email):
    user = User(
        full_name=f"Offline Sync {role}",
        email=email,
        role=role,
    )
    setattr(user, "password", hash_password(PASSWORD))
    test_db.add(user)
    test_db.commit()

    response = client.post(
        "/users/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _asset(test_db, *, suffix):
    asset = AssetRegistry(
        sal_id=f"SAL-OFFLINE-{suffix}",
        asset_type="Vehicle",
        registry_id=int(suffix),
        owner="Original Owner",
        estimated_value=1000.0,
        status="Active",
        sal_verification="VERIFIED",
        government_verification="NOT_VERIFIED",
    )
    test_db.add(asset)
    test_db.commit()
    test_db.refresh(asset)
    return asset


def _operation(asset, *, changes, expected_version=1, operation_id=None):
    return {
        "operation_id": operation_id or str(uuid.uuid4()),
        "asset_registry_id": asset.id,
        "expected_version": expected_version,
        "changes": changes,
    }


def test_sync_is_idempotent_and_audits_accepted_operation(client, test_db):
    headers = _login(
        client,
        test_db,
        role="registrar",
        email="offline-idempotent@sal.test",
    )
    asset = _asset(test_db, suffix="801")
    operation = _operation(asset, changes={"status": "Inactive"})

    first = client.post(
        "/offline-sync/batches",
        json={"operations": [operation]},
        headers=headers,
    )
    retry = client.post(
        "/offline-sync/batches",
        json={"operations": [operation]},
        headers=headers,
    )

    assert first.status_code == 200
    assert first.json()["results"][0]["outcome"] == "ACCEPTED"
    assert retry.json()["results"][0]["outcome"] == "DUPLICATE"
    test_db.refresh(asset)
    assert asset.status == "Inactive"
    assert asset.version == 2
    assert (
        test_db.query(AuditEvent)
        .filter(AuditEvent.action == "OFFLINE_SYNC_OPERATION_ACCEPTED")
        .count()
        == 1
    )


def test_partial_batch_failure_does_not_discard_valid_operation(client, test_db):
    headers = _login(
        client,
        test_db,
        role="registrar",
        email="offline-partial@sal.test",
    )
    asset = _asset(test_db, suffix="802")
    response = client.post(
        "/offline-sync/batches",
        json={
            "operations": [
                _operation(asset, changes={"estimated_value": 1200}),
                _operation(asset, changes={"unexpected_field": True}),
            ]
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert [result["outcome"] for result in response.json()["results"]] == [
        "ACCEPTED",
        "REJECTED",
    ]
    test_db.refresh(asset)
    assert asset.estimated_value == 1200
    assert asset.version == 2
    assert test_db.query(OfflineSyncOperation).count() == 2


def test_owner_change_requires_review_and_is_audited(client, test_db):
    headers = _login(
        client,
        test_db,
        role="registrar",
        email="offline-owner-review@sal.test",
    )
    asset = _asset(test_db, suffix="803")
    response = client.post(
        "/offline-sync/batches",
        json={
            "operations": [
                _operation(asset, changes={"owner": "Submitted Owner"})
            ]
        },
        headers=headers,
    )

    result = response.json()["results"][0]
    assert result["outcome"] == "CONFLICT"
    assert result["conflict_id"] is not None
    test_db.refresh(asset)
    assert asset.owner == "Original Owner"

    resolved = client.post(
        f"/offline-sync/conflicts/{result['conflict_id']}/resolution",
        json={"resolution": "ACCEPT", "note": "Reviewed supporting record"},
        headers=headers,
    )

    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    test_db.refresh(asset)
    assert asset.owner == "Submitted Owner"
    assert asset.version == 2
    assert (
        test_db.query(AuditEvent)
        .filter(AuditEvent.action == "OFFLINE_SYNC_CONFLICT_RESOLVED")
        .count()
        == 1
    )


def test_concurrent_operations_conflict_and_can_be_reviewed(client, test_db):
    headers = _login(
        client,
        test_db,
        role="admin",
        email="offline-concurrent@sal.test",
    )
    asset = _asset(test_db, suffix="804")
    response = client.post(
        "/offline-sync/batches",
        json={
            "operations": [
                _operation(asset, changes={"status": "Pending"}),
                _operation(asset, changes={"status": "Under Review"}),
            ]
        },
        headers=headers,
    )

    accepted, conflicted = response.json()["results"]
    assert accepted["outcome"] == "ACCEPTED"
    assert conflicted["outcome"] == "CONFLICT"
    test_db.refresh(asset)
    assert asset.status == "Pending"
    assert asset.version == 2

    resolved = client.post(
        f"/offline-sync/conflicts/{conflicted['conflict_id']}/resolution",
        json={"resolution": "ACCEPT", "note": "Reviewed and rebased"},
        headers=headers,
    )
    assert resolved.status_code == 200
    test_db.refresh(asset)
    assert asset.status == "Under Review"
    assert asset.version == 3


def test_duplicate_vin_submission_is_preserved_and_rejected(client, test_db):
    headers = _login(
        client,
        test_db,
        role="registrar",
        email="offline-duplicate-vin@sal.test",
    )
    existing_asset = _asset(test_db, suffix="805")
    submitted_asset = _asset(test_db, suffix="806")
    test_db.add(
        AssetExternalIdentifier(
            asset_registry_id=existing_asset.id,
            authority="SAL",
            identifier_type="VIN",
            identifier_value="DUPLICATEVIN1234567",
            status="ACTIVE",
        )
    )
    test_db.commit()

    response = client.post(
        "/offline-sync/batches",
        json={
            "operations": [
                _operation(
                    submitted_asset,
                    changes={
                        "identifier": {
                            "type": "VIN",
                            "value": "duplicatevin1234567",
                        }
                    },
                )
            ]
        },
        headers=headers,
    )
    result = response.json()["results"][0]
    assert result["outcome"] == "CONFLICT"
    conflict = (
        test_db.query(OfflineSyncConflict)
        .filter(OfflineSyncConflict.id == result["conflict_id"])
        .one()
    )
    assert json.loads(conflict.submission_payload)["changes"]["identifier"]["value"] == (
        "duplicatevin1234567"
    )

    resolution = client.post(
        f"/offline-sync/conflicts/{conflict.id}/resolution",
        json={"resolution": "REJECT", "note": "Identifier belongs to another asset"},
        headers=headers,
    )
    assert resolution.status_code == 200
    assert resolution.json()["resolution"] == "REJECT"


def test_reused_operation_id_preserves_submission_without_changing_original(
    client,
    test_db,
):
    headers = _login(
        client,
        test_db,
        role="registrar",
        email="offline-operation-id-reuse@sal.test",
    )
    asset = _asset(test_db, suffix="807")
    operation_id = str(uuid.uuid4())
    original = _operation(
        asset,
        changes={"status": "Original"},
        operation_id=operation_id,
    )
    client.post(
        "/offline-sync/batches",
        json={"operations": [original]},
        headers=headers,
    )
    reused = _operation(
        asset,
        changes={"status": "Conflicting"},
        operation_id=operation_id,
    )
    response = client.post(
        "/offline-sync/batches",
        json={"operations": [reused]},
        headers=headers,
    )

    result = response.json()["results"][0]
    assert result["outcome"] == "CONFLICT"
    assert json.loads(
        test_db.query(OfflineSyncConflict)
        .filter(OfflineSyncConflict.id == result["conflict_id"])
        .one()
        .submission_payload
    )["changes"]["status"] == "Conflicting"

    resolved = client.post(
        f"/offline-sync/conflicts/{result['conflict_id']}/resolution",
        json={"resolution": "REJECT", "note": "Operation ID already used"},
        headers=headers,
    )
    assert resolved.status_code == 200
    original_record = (
        test_db.query(OfflineSyncOperation)
        .filter(OfflineSyncOperation.operation_id == operation_id)
        .one()
    )
    assert original_record.status == "ACCEPTED"
    test_db.refresh(asset)
    assert asset.status == "Original"


def test_sync_requires_authorized_user_and_bounds_batch(client, test_db):
    viewer_headers = _login(
        client,
        test_db,
        role="viewer",
        email="offline-viewer@sal.test",
    )
    asset = _asset(test_db, suffix="808")

    unauthorized = client.post(
        "/offline-sync/batches",
        json={"operations": [_operation(asset, changes={"status": "Pending"})]},
        headers=viewer_headers,
    )
    unauthenticated = client.post(
        "/offline-sync/batches",
        json={"operations": [_operation(asset, changes={"status": "Pending"})]},
    )
    oversized = client.post(
        "/offline-sync/batches",
        json={
            "operations": [
                _operation(asset, changes={"status": "Pending"})
                for _ in range(101)
            ]
        },
        headers=viewer_headers,
    )

    assert unauthorized.status_code == 403
    assert unauthenticated.status_code == 401
    assert oversized.status_code == 422
    assert test_db.query(OfflineSyncOperation).count() == 0
