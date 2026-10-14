from uuid import uuid4

from app.core.security import hash_password
from app.models.asset import Asset
from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.models.diamond import Diamond
from app.models.gold import Gold
from app.models.land import Land
from app.models.offline_sync import OfflineSyncConflict, OfflineSyncOperation
from app.models.user import User
from app.models.vehicle import Vehicle


def login(client, test_db, *, email, role):
    user = User(
        full_name=f"Offline Sync {role}",
        email=email,
        ******"Offline-Sync-Test-Password"),
        role=role,
    )
    test_db.add(user)
    test_db.commit()

    response = client.post(
        "/users/login",
        data={"username": email, "password": "Offline-Sync-Test-Password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"******'access_token']}"}


def operation(asset_type, data, operation_id=None):
    return {
        "operation_id": operation_id or str(uuid4()),
        "operation": "create",
        "asset_type": asset_type,
        "data": data,
    }


def sample_payloads():
    suffix = uuid4().hex[:10].upper()
    return {
        "asset": {
            "owner": "Claimed generic owner",
            "asset_name": f"Offline asset {suffix}",
            "value": 200.0,
        },
        "land": {
            "parcel_number": f"PARCEL-{suffix}",
            "owner_name": "Claimed land owner",
            "community": "Community",
            "district": "District",
            "region": "Region",
            "size": 2.5,
            "land_use": "Residential",
            "estimated_value": 1200.0,
        },
        "vehicle": {
            "owner": "Claimed vehicle owner",
            "registration_number": f"REG-{suffix}",
            "vin": f"VIN{suffix}000000000000",
            "manufacturer": "Manufacturer",
            "model": "Model",
            "year": 2024,
            "engine_number": f"ENGINE-{suffix}",
            "color": "Blue",
            "estimated_value": 25000.0,
        },
        "gold": {
            "owner": "Claimed gold owner",
            "type": "Bar",
            "purity": "24K",
            "weight": 100.0,
            "estimated_value": 6500.0,
            "serial_number": f"GOLD-{suffix}",
        },
        "diamond": {
            "owner": "Claimed diamond owner",
            "gemstone": "Diamond",
            "carat": 1.5,
            "cut": "Round",
            "color": "D",
            "clarity": "VVS1",
            "certificate_number": f"CERT-{suffix}",
            "estimated_value": 9000.0,
        },
    }


def test_offline_batch_requires_authentication(client):
    response = client.post("/offline-sync/batches", json={"operations": []})
    assert response.status_code == 401


def test_offline_create_supported_asset_types_are_pending_and_idempotent(
    client, test_db
):
    headers = login(
        client,
        test_db,
        email="offline-registrar@sal.test",
        role="registrar",
    )
    payloads = sample_payloads()
    operations = [
        operation(asset_type, data)
        for asset_type, data in payloads.items()
    ]

    response = client.post(
        "/offline-sync/batches",
        json={"operations": operations},
        headers=headers,
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["status"] for result in results] == ["created"] * 5
    assert all(result["sal_id"] for result in results)
    assert test_db.query(Asset).count() == 1
    assert test_db.query(Land).count() == 1
    assert test_db.query(Vehicle).count() == 1
    assert test_db.query(Gold).count() == 1
    assert test_db.query(Diamond).count() == 1

    registries = test_db.query(AssetRegistry).order_by(AssetRegistry.id).all()
    assert len(registries) == 5
    assert all(row.status == "PENDING_REVIEW" for row in registries)
    assert all(row.sal_verification == "PENDING" for row in registries)
    assert test_db.query(Land).first().approval_status == "Pending"
    assert test_db.query(Vehicle).first().status == "PENDING_REVIEW"
    assert test_db.query(Gold).first().status == "PENDING_REVIEW"
    assert test_db.query(Diamond).first().status == "PENDING_REVIEW"

    retry = client.post(
        "/offline-sync/batches",
        json={"operations": operations},
        headers=headers,
    )
    assert retry.status_code == 200
    assert retry.json()["results"] == results
    assert test_db.query(OfflineSyncOperation).count() == 5
    assert test_db.query(Asset).count() == 1
    assert (
        test_db.query(AuditEvent)
        .filter(AuditEvent.action == "offline.duplicate_submission")
        .count()
        == 5
    )


def test_viewer_is_rejected_and_invalid_item_does_not_abort_batch(client, test_db):
    headers = login(
        client,
        test_db,
        email="offline-viewer@sal.test",
        role="viewer",
    )
    generic = sample_payloads()["asset"]
    invalid_land = sample_payloads()["land"]
    invalid_land["unexpected"] = "not allowed"

    response = client.post(
        "/offline-sync/batches",
        json={
            "operations": [
                operation("asset", generic),
                operation("land", invalid_land),
                {"operation_id": "not-a-uuid", "operation": "create"},
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["status"] for result in results] == [
        "rejected",
        "rejected",
        "rejected",
    ]
    assert test_db.query(Asset).count() == 0
    assert test_db.query(Land).count() == 0
    assert (
        test_db.query(AuditEvent)
        .filter(AuditEvent.action == "offline.operation_rejected")
        .count()
        == 3
    )


def test_duplicate_unique_identifiers_preserve_conflicts_and_require_admin_review(
    client, test_db
):
    headers = login(
        client,
        test_db,
        email="offline-admin@sal.test",
        role="admin",
    )
    payloads = sample_payloads()
    initial_operations = [
        operation(asset_type, payloads[asset_type])
        for asset_type in ("land", "vehicle", "gold", "diamond")
    ]
    first = client.post(
        "/offline-sync/batches",
        json={"operations": initial_operations},
        headers=headers,
    )
    assert first.status_code == 200
    assert all(row["status"] == "created" for row in first.json()["results"])

    duplicate_payloads = {
        "land": {**payloads["land"], "owner_name": "Second claim"},
        "vehicle": {
            **payloads["vehicle"],
            "registration_number": "DIFFERENT-REGISTRATION",
        },
        "gold": {**payloads["gold"], "owner": "Second claim"},
        "diamond": {**payloads["diamond"], "owner": "Second claim"},
    }
    duplicates = [
        operation(asset_type, duplicate_payloads[asset_type])
        for asset_type in ("land", "vehicle", "gold", "diamond")
    ]
    response = client.post(
        "/offline-sync/batches",
        json={"operations": duplicates},
        headers=headers,
    )
    assert response.status_code == 200
    assert [item["status"] for item in response.json()["results"]] == [
        "conflict",
        "conflict",
        "conflict",
        "conflict",
    ]
    assert test_db.query(Land).count() == 1
    assert test_db.query(Vehicle).count() == 1
    assert test_db.query(Gold).count() == 1
    assert test_db.query(Diamond).count() == 1
    assert test_db.query(OfflineSyncConflict).count() == 4

    conflict_id = response.json()["results"][0]["conflict_id"]
    listed = client.get("/offline-sync/conflicts", headers=headers)
    assert listed.status_code == 200
    preserved = next(row for row in listed.json() if row["id"] == conflict_id)
    assert preserved["submitted_payload"]["data"]["owner_name"] == "Second claim"
    assert preserved["identifier_type"] == "parcel_number"

    viewer_headers = login(
        client,
        test_db,
        email="offline-conflict-viewer@sal.test",
        role="viewer",
    )
    forbidden = client.post(
        f"/offline-sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "reject_submission"},
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403

    resolved = client.post(
        f"/offline-sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "reject_submission"},
        headers=headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolution"] == "reject_submission"
    assert test_db.query(Land).count() == 1
    assert (
        test_db.query(AuditEvent)
        .filter(AuditEvent.action == "offline.conflict_resolved")
        .count()
        == 1
    )


def test_operation_uuid_is_scoped_to_user_and_changed_payload_is_a_conflict(
    client, test_db
):
    headers = login(
        client,
        test_db,
        email="offline-owner@sal.test",
        role="registrar",
    )
    operation_id = str(uuid4())
    submitted = operation("asset", sample_payloads()["asset"], operation_id)
    first = client.post(
        "/offline-sync/batches",
        json={"operations": [submitted]},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["results"][0]["status"] == "created"

    changed = operation(
        "asset",
        {
            "owner": "Different claim",
            "asset_name": "Different asset",
            "value": 1000.0,
        },
        operation_id,
    )
    mismatch = client.post(
        "/offline-sync/batches",
        json={"operations": [changed]},
        headers=headers,
    )
    assert mismatch.status_code == 200
    assert mismatch.json()["results"][0]["status"] == "conflict"
    assert test_db.query(Asset).count() == 1
    assert test_db.query(OfflineSyncConflict).count() == 1
    assert test_db.query(OfflineSyncOperation).count() == 1

    other_headers = login(
        client,
        test_db,
        email="offline-other-registrar@sal.test",
        role="registrar",
    )
    other_user_result = client.post(
        "/offline-sync/batches",
        json={"operations": [submitted]},
        headers=other_headers,
    )
    assert other_user_result.status_code == 200
    assert other_user_result.json()["results"][0]["status"] == "created"
    assert test_db.query(Asset).count() == 2


def test_batch_and_body_size_limits(client, test_db):
    headers = login(
        client,
        test_db,
        email="offline-limits@sal.test",
        role="admin",
    )
    too_many = client.post(
        "/offline-sync/batches",
        json={"operations": [{}] * 101},
        headers=headers,
    )
    assert too_many.status_code == 422

    too_large = client.post(
        "/offline-sync/batches",
        content=b'{"operations":[]}' + (b" " * 1_048_577),
        headers={**headers, "Content-Type": "application/json"},
    )
    assert too_large.status_code == 413
