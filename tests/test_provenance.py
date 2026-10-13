import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.blockchain.provider import MockLedgerProvider
from app.core.config import settings
from app.core.security import hash_password
from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.models.provenance_commitment import (
    ProvenanceAnchorAttempt,
    ProvenanceCommitment,
)
from app.models.user import User
from app.services.provenance_service import (
    calculate_commitment,
    canonical_event_document,
    canonicalize,
    create_commitment,
    process_anchor,
    verify_commitment,
)


def create_event(db, *, event_id="SAL-EVENT-PROV-001", after_data=None, asset=None):
    if asset is None:
        asset = AssetRegistry(
            sal_id="SAL-PROV-ASSET-001",
            asset_type="LAND",
            registry_id=42,
            owner="Private Owner",
            status="Active",
        )
        db.add(asset)
        db.flush()

    event = AuditEvent(
        event_id=event_id,
        actor_id=19,
        actor_type="USER",
        action="OWNERSHIP_CHANGE_APPROVED",
        entity_type="ASSET_REGISTRY",
        entity_id=asset.sal_id,
        asset_registry_id=asset.id,
        passport_id=None,
        occurred_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        source="API",
        ip_address="192.0.2.10",
        result="SUCCESS",
        before_data=json.dumps({"owner": "Previous Owner"}),
        after_data=json.dumps(
            after_data or {"owner": "Private Owner", "version": 2}
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_canonicalization_is_deterministic_and_commitment_is_nonce_bound():
    left = {"version": 2, "state": "ACTIVE"}
    right = {"state": "ACTIVE", "version": 2}

    assert canonicalize(left) == canonicalize(right)
    assert calculate_commitment(left, "ab" * 32) == calculate_commitment(
        right, "ab" * 32
    )
    assert calculate_commitment(left, "ab" * 32) != calculate_commitment(
        left, "cd" * 32
    )


def test_canonical_event_document_excludes_actor_and_network_metadata(test_db):
    event = create_event(test_db)

    document = canonical_event_document(event, "SAL-PROV-ASSET-001")
    encoded = canonicalize(document).decode()

    assert document["format_version"] == 1
    assert document["asset_id"] == "SAL-PROV-ASSET-001"
    assert "actor_id" not in document
    assert "ip_address" not in document
    assert "192.0.2.10" not in encoded


def test_create_anchor_and_verify_commitment(test_db, monkeypatch):
    monkeypatch.setattr(settings, "SAL_PROVENANCE_SIGNING_KEY", "k" * 64)
    monkeypatch.setattr(
        settings,
        "SAL_PROVENANCE_SIGNER_KEY_ID",
        "institutional-test",
    )
    event = create_event(test_db)

    commitment = create_commitment(test_db, event)
    test_db.commit()
    process_anchor(test_db, commitment)
    test_db.commit()

    result = verify_commitment(test_db, commitment)
    assert commitment.anchor_status == "CONFIRMED"
    assert commitment.signature is not None
    assert result == {
        "commitment_id": commitment.commitment_id,
        "commitment_valid": True,
        "signature_valid": True,
        "anchor_valid": True,
        "verified": True,
        "legal_ownership_verified": False,
    }


def test_tampered_audit_event_fails_verification(test_db):
    event = create_event(test_db)
    commitment = create_commitment(test_db, event)
    test_db.commit()
    process_anchor(test_db, commitment)
    test_db.commit()

    with test_db.get_bind().begin() as connection:
        connection.exec_driver_sql(
            "DROP TRIGGER IF EXISTS trg_audit_events_prevent_update"
        )
        connection.execute(
            text(
                "UPDATE audit_events SET after_data = :after_data "
                "WHERE event_id = :event_id"
            ),
            {
                "after_data": json.dumps({"owner": "Tampered Owner", "version": 2}),
                "event_id": event.event_id,
            },
        )
    test_db.expire_all()

    result = verify_commitment(test_db, commitment)
    assert result["commitment_valid"] is False
    assert result["verified"] is False


def test_invalid_signature_is_reported_and_not_verified(test_db, monkeypatch):
    monkeypatch.setattr(settings, "SAL_PROVENANCE_SIGNING_KEY", "k" * 64)
    monkeypatch.setattr(
        settings,
        "SAL_PROVENANCE_SIGNER_KEY_ID",
        "institutional-test",
    )
    event = create_event(test_db)
    commitment = create_commitment(test_db, event)
    test_db.commit()
    process_anchor(test_db, commitment)
    test_db.commit()
    commitment.signature = "00" * 32
    test_db.commit()

    result = verify_commitment(test_db, commitment)
    assert result["signature_valid"] is False
    assert result["verified"] is False


def test_duplicate_requests_reuse_commitment_and_versions_link(test_db):
    first_event = create_event(test_db)
    first = create_commitment(test_db, first_event)
    test_db.commit()
    assert create_commitment(test_db, first_event).id == first.id

    asset = test_db.get(AssetRegistry, first_event.asset_registry_id)
    second_event = create_event(
        test_db,
        event_id="SAL-EVENT-PROV-002",
        after_data={"owner": "New Private Owner", "version": 3},
        asset=asset,
    )
    second = create_commitment(test_db, second_event)
    assert second.previous_commitment_id == first.commitment_id
    assert second.record_version == 3


def test_failed_anchor_can_be_retried_and_attempts_are_recorded(test_db):
    event = create_event(test_db)
    commitment = create_commitment(test_db, event)
    test_db.commit()

    class FailingProvider:
        provider_name = "mock-ledger"
        network_id = "sal-mocknet-v1"

        def anchor(self, commitment_hash):
            raise TimeoutError("not persisted")

        def verify(self, commitment_hash, reference):
            return False

    process_anchor(test_db, commitment, provider=FailingProvider())
    test_db.commit()
    assert commitment.anchor_status == "FAILED"
    assert commitment.anchor_attempts == 1
    assert commitment.last_anchor_error == "TimeoutError"

    process_anchor(test_db, commitment, provider=MockLedgerProvider())
    test_db.commit()
    assert commitment.anchor_status == "CONFIRMED"
    assert commitment.anchor_attempts == 2
    assert (
        test_db.query(ProvenanceAnchorAttempt)
        .filter(ProvenanceAnchorAttempt.commitment_id == commitment.id)
        .count()
        == 2
    )


def test_database_rollback_does_not_leave_uncommitted_commitment(test_db):
    event = create_event(test_db)
    commitment = create_commitment(test_db, event)
    commitment_id = commitment.commitment_id
    test_db.rollback()

    assert (
        test_db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.commitment_id == commitment_id)
        .first()
        is None
    )


def create_user_and_login(client, test_db, role, email):
    password = "Strong-Test-Password-123!"
    user = User(
        full_name="Provenance Test",
        email=email,
        ******
        role=role,
    )
    test_db.add(user)
    test_db.commit()
    response = client.post(
        "/users/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"******'access_token']}"}


def test_authorized_commitment_api_is_idempotent_and_hides_snapshot(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        "registrar",
        "provenance-registrar@sal.test",
    )
    event = create_event(test_db)

    first_response = client.post(
        f"/provenance/events/{event.event_id}/commitment",
        headers=headers,
    )
    second_response = client.post(
        f"/provenance/events/{event.event_id}/commitment",
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first = first_response.json()
    second = second_response.json()
    assert first["commitment_id"] == second["commitment_id"]
    assert first["anchor_status"] == "CONFIRMED"
    assert "Private Owner" not in first_response.text
    assert "before_data" not in first


def test_provenance_requires_authorization(client, test_db):
    assert client.get("/provenance/commitments/unknown").status_code == 401
    headers = create_user_and_login(
        client,
        test_db,
        "viewer",
        "provenance-viewer@sal.test",
    )
    assert (
        client.get(
            "/provenance/commitments/unknown",
            headers=headers,
        ).status_code
        == 403
    )
