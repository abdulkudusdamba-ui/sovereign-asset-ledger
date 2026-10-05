import json
from datetime import datetime, timezone

from app.core.security import hash_password
from app.models.audit_event import AuditEvent
from app.models.user import User


def create_user_and_login(
    client,
    test_db,
    *,
    email,
    role,
    password,
):
    user = User(
        full_name=f"SAL Audit {role.title()}",
        email=email,
        password=hash_password(password),
        role=role,
    )

    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    response = client.post(
        "/users/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_audit_event(
    db,
    *,
    event_id,
    actor_id=1,
    action="EVIDENCE_REVIEW",
    entity_type="ASSET_EVIDENCE",
    entity_id="1",
    asset_registry_id=1,
    passport_id=1,
    result="SUCCESS",
    reference=None,
):
    event = AuditEvent(
        event_id=event_id,
        actor_id=actor_id,
        actor_type="USER",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        asset_registry_id=asset_registry_id,
        passport_id=passport_id,
        occurred_at=datetime.now(timezone.utc),
        source="API",
        reason="Test audit event",
        reference=reference,
        result=result,
        before_data=json.dumps({"status": "SUBMITTED"}),
        after_data=json.dumps({"status": "UNDER_REVIEW"}),
        audit_metadata=json.dumps({"test": True}),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def test_admin_can_read_audit_events(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-admin@sal.test",
        role="admin",
        password="SAL-Audit-Admin-2026",
    )

    create_audit_event(
        test_db,
        event_id="SAL-EVENT-API-ADMIN-001",
    )

    response = client.get(
        "/audit/events",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert any(
        event["event_id"] == "SAL-EVENT-API-ADMIN-001"
        for event in data
    )


def test_registrar_can_read_audit_events(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-registrar@sal.test",
        role="registrar",
        password="SAL-Audit-Registrar-2026",
    )

    create_audit_event(
        test_db,
        event_id="SAL-EVENT-API-REGISTRAR-001",
    )

    response = client.get(
        "/audit/events",
        headers=headers,
    )

    assert response.status_code == 200


def test_government_can_read_audit_events(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-government@sal.test",
        role="government",
        password="SAL-Audit-Government-2026",
    )

    create_audit_event(
        test_db,
        event_id="SAL-EVENT-API-GOV-001",
    )

    response = client.get(
        "/audit/events",
        headers=headers,
    )

    assert response.status_code == 200


def test_viewer_cannot_read_audit_events(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-viewer@sal.test",
        role="viewer",
        password="SAL-Audit-Viewer-2026",
    )

    response = client.get(
        "/audit/events",
        headers=headers,
    )

    assert response.status_code == 403


def test_unauthenticated_cannot_read_audit_events(client):
    response = client.get("/audit/events")

    assert response.status_code == 401


def test_audit_events_support_filters(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-filter-admin@sal.test",
        role="admin",
        password="SAL-Audit-Filter-2026",
    )

    create_audit_event(
        test_db,
        event_id="SAL-EVENT-FILTER-MATCH",
        action="PASSPORT_LIFECYCLE",
        entity_type="ASSET_PASSPORT",
        entity_id="PASSPORT-1",
        asset_registry_id=99,
        passport_id=77,
        reference="REF-MATCH",
    )

    create_audit_event(
        test_db,
        event_id="SAL-EVENT-FILTER-NOMATCH",
        action="EVIDENCE_REVIEW",
        entity_type="ASSET_EVIDENCE",
        entity_id="EVIDENCE-2",
        asset_registry_id=100,
        passport_id=78,
    )

    response = client.get(
        "/audit/events",
        params={
            "asset_registry_id": 99,
            "passport_id": 77,
            "action": "PASSPORT_LIFECYCLE",
            "entity_type": "ASSET_PASSPORT",
            "entity_id": "PASSPORT-1",
            "reference": "REF-MATCH",
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["event_id"] == "SAL-EVENT-FILTER-MATCH"


def test_audit_events_support_pagination(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-pagination-admin@sal.test",
        role="admin",
        password="SAL-Audit-Pagination-2026",
    )

    for index in range(5):
        create_audit_event(
            test_db,
            event_id=f"SAL-EVENT-PAGE-{index}",
            entity_id=str(index),
        )

    response = client.get(
        "/audit/events",
        params={
            "limit": 2,
            "offset": 1,
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2


def test_audit_events_endpoint_is_read_only(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="audit-readonly-admin@sal.test",
        role="admin",
        password="SAL-Audit-Readonly-2026",
    )

    post_response = client.post(
        "/audit/events",
        headers=headers,
        json={},
    )

    patch_response = client.patch(
        "/audit/events",
        headers=headers,
        json={},
    )

    delete_response = client.delete(
        "/audit/events",
        headers=headers,
    )

    assert post_response.status_code == 405
    assert patch_response.status_code == 405
    assert delete_response.status_code == 405


def test_database_rejects_audit_event_update(test_db):
    from sqlalchemy.exc import IntegrityError

    event = create_audit_event(
        test_db,
        event_id="SAL-EVENT-IMMUTABLE-UPDATE",
    )

    event.result = "TAMPERED"

    try:
        test_db.commit()
    except Exception as exc:
        test_db.rollback()
        assert "immutable" in str(exc).lower()
    else:
        raise AssertionError(
            "Database allowed an immutable audit event UPDATE"
        )


def test_database_rejects_audit_event_delete(test_db):
    event = create_audit_event(
        test_db,
        event_id="SAL-EVENT-IMMUTABLE-DELETE",
    )

    test_db.delete(event)

    try:
        test_db.commit()
    except Exception as exc:
        test_db.rollback()
        assert "immutable" in str(exc).lower()
    else:
        raise AssertionError(
            "Database allowed an immutable audit event DELETE"
        )
