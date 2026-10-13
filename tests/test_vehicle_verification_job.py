from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.models.government_verification import GovernmentVerification
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_verification_job import VehicleVerificationJob
from app.providers.vehicle_authority_provider import (
    FakeVehicleAuthorityProvider,
    ProviderPermanentError,
    ProviderUnavailableError,
    VehicleAuthorityRecord,
    get_vehicle_authority_provider,
)
from app.routers import vehicle_verification_job as router_module
from app.services import vehicle_verification_job_service as service


PASSWORD = "Test-Password-123"


def login(client, db, email, role):
    user = User(
        full_name=f"VVJ {role}",
        email=email,
        password=hash_password(PASSWORD),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    response = client.post(
        "/users/login", data={"username": email, "password": PASSWORD}
    )
    assert response.status_code == 200

    token = response.json()["access_token"]

    return user, {"Authorization": "Bearer " + token}


def make_asset(db, n=1, vin=None, asset_type="Vehicle"):
    vehicle = Vehicle(
        owner="Secret Owner Name",
        registration_number=f"GT-VVJ-{n}",
        vin=vin or f"VVJVIN{n:04d}",
        chassis_number=f"CHASSIS{n:04d}",
        engine_number=f"ENGINE{n:04d}",
    )
    db.add(vehicle)
    db.flush()
    asset = AssetRegistry(
        sal_id=f"SAL-VVJ-ASSET-{n}",
        asset_type=asset_type,
        registry_id=vehicle.id,
        owner="Secret Owner Name",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@pytest.fixture()
def enqueued(monkeypatch):
    calls = []
    monkeypatch.setattr(router_module, "enqueue_job", calls.append)
    return calls


def audit_actions(db):
    return [
        e.action
        for e in db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "VehicleVerificationJob")
        .order_by(AuditEvent.id)
        .all()
    ]


def new_job(db, asset, user, key=None):
    job, _ = service.create_job(
        db, sal_id=asset.sal_id, user=user, idempotency_key=key
    )
    return job


# ---------- API: creation, validation, authorization ----------


def test_create_pending_job(client, test_db, enqueued):
    user, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)

    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers=headers,
    )

    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "PENDING"
    assert data["outcome"] is None
    assert data["provider"] == "FAKE"
    assert data["sal_id"] == asset.sal_id
    assert "Secret Owner Name" not in r.text
    assert enqueued == [data["job_id"]]
    test_db.refresh(asset)
    assert asset.government_verification == "NOT_VERIFIED"
    assert audit_actions(test_db) == ["VEHICLE_VERIFICATION_JOB_CREATED"]


def test_nonexistent_asset_rejected(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": "NOPE"},
        headers=headers,
    )
    assert r.status_code == 404
    assert test_db.query(VehicleVerificationJob).count() == 0
    assert enqueued == []


def test_non_vehicle_asset_rejected(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db, asset_type="Land")
    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers=headers,
    )
    assert r.status_code == 422
    assert test_db.query(VehicleVerificationJob).count() == 0


def test_registry_without_vehicle_conflicts(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)
    asset.registry_id = 9999
    test_db.commit()
    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers=headers,
    )
    assert r.status_code == 409


def test_authorization(client, test_db, enqueued):
    asset = make_asset(test_db)
    body = {"sal_id": asset.sal_id}

    assert (
        client.post("/vehicle-verification-jobs", json=body).status_code
        == 401
    )

    _, viewer = login(client, test_db, "v@vvj.test", "viewer")
    _, gov = login(client, test_db, "g@vvj.test", "government")
    _, reg = login(client, test_db, "r@vvj.test", "registrar")

    assert (
        client.post(
            "/vehicle-verification-jobs", json=body, headers=viewer
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/vehicle-verification-jobs", json=body, headers=gov
        ).status_code
        == 403
    )

    r = client.post("/vehicle-verification-jobs", json=body, headers=reg)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    url = f"/vehicle-verification-jobs/{job_id}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=viewer).status_code == 403
    assert client.get(url, headers=gov).status_code == 200
    assert client.get(url, headers=reg).status_code == 200
    assert (
        client.get(
            "/vehicle-verification-jobs/missing", headers=reg
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"status": "COMPLETED"},
        {"outcome": "MATCH"},
        {"mismatched_fields": []},
        {"attempt_count": 0},
        {"provider": "DVLA"},
    ],
)
def test_client_cannot_set_server_fields(client, test_db, enqueued, extra):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)
    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id, **extra},
        headers=headers,
    )
    assert r.status_code == 422
    assert test_db.query(VehicleVerificationJob).count() == 0


def test_no_mutation_endpoints(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)
    job_id = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers=headers,
    ).json()["job_id"]
    url = f"/vehicle-verification-jobs/{job_id}"
    body = {"status": "COMPLETED"}
    assert client.patch(url, json=body, headers=headers).status_code == 405
    assert client.put(url, json=body, headers=headers).status_code == 405
    assert client.delete(url, headers=headers).status_code == 405


def test_invalid_idempotency_key(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)
    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers={**headers, "Idempotency-Key": "bad key!"},
    )
    assert r.status_code == 422


# ---------- idempotency ----------


def test_same_key_same_asset_returns_same_job(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)
    h = {**headers, "Idempotency-Key": "key-1"}
    body = {"sal_id": asset.sal_id}

    r1 = client.post("/vehicle-verification-jobs", json=body, headers=h)
    r2 = client.post("/vehicle-verification-jobs", json=body, headers=h)

    assert r1.status_code == 202
    assert r2.status_code == 200
    assert r1.json()["job_id"] == r2.json()["job_id"]
    assert test_db.query(VehicleVerificationJob).count() == 1
    assert audit_actions(test_db) == ["VEHICLE_VERIFICATION_JOB_CREATED"]


def test_same_key_different_asset_rejected(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    a1, a2 = make_asset(test_db, 1), make_asset(test_db, 2)
    h = {**headers, "Idempotency-Key": "key-1"}
    client.post(
        "/vehicle-verification-jobs", json={"sal_id": a1.sal_id}, headers=h
    )
    r = client.post(
        "/vehicle-verification-jobs", json={"sal_id": a2.sal_id}, headers=h
    )
    assert r.status_code == 409
    assert test_db.query(VehicleVerificationJob).count() == 1


def test_one_active_job_per_asset(client, test_db, enqueued):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)
    body = {"sal_id": asset.sal_id}
    r1 = client.post("/vehicle-verification-jobs", json=body, headers=headers)
    r2 = client.post("/vehicle-verification-jobs", json=body, headers=headers)
    assert r1.json()["job_id"] == r2.json()["job_id"]
    assert test_db.query(VehicleVerificationJob).count() == 1


def test_db_constraint_blocks_second_active_job(test_db):
    asset = make_asset(test_db)
    for n in (1, 2):
        test_db.add(
            VehicleVerificationJob(
                job_id=f"J{n}",
                asset_registry_id=asset.id,
                provider="FAKE",
                status="PENDING",
                attempt_count=0,
            )
        )
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_new_job_allowed_after_terminal(test_db):
    user = User(full_name="u", email="u@x", password=hash_password(PASSWORD), role="admin")
    test_db.add(user)
    test_db.commit()
    asset = make_asset(test_db)
    j1 = new_job(test_db, asset, user)
    service.process_job(test_db, j1.job_id, FakeVehicleAuthorityProvider())
    j2 = new_job(test_db, asset, user)
    assert j2.job_id != j1.job_id
    assert j2.status == "PENDING"


# ---------- enqueue failure ----------


def test_enqueue_failure_leaves_job_pending(client, test_db, monkeypatch):
    _, headers = login(client, test_db, "a@vvj.test", "admin")
    asset = make_asset(test_db)

    def boom(job_id):
        raise RuntimeError("broker down")

    monkeypatch.setattr(router_module, "enqueue_job", boom)
    r = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers=headers,
    )
    assert r.status_code == 202
    assert r.json()["status"] == "PENDING"
    assert audit_actions(test_db) == [
        "VEHICLE_VERIFICATION_JOB_CREATED",
        "VEHICLE_VERIFICATION_JOB_ENQUEUE_FAILED",
    ]

    # Repeating the request re-enqueues the still-pending job.
    calls = []
    monkeypatch.setattr(router_module, "enqueue_job", calls.append)
    r2 = client.post(
        "/vehicle-verification-jobs",
        json={"sal_id": asset.sal_id},
        headers=headers,
    )
    assert r2.json()["job_id"] == r.json()["job_id"]
    assert calls == [r.json()["job_id"]]


# ---------- processing ----------


@pytest.fixture()
def user(test_db):
    u = User(full_name="u", email="u@x", password=hash_password(PASSWORD), role="admin")
    test_db.add(u)
    test_db.commit()
    test_db.refresh(u)
    return u


def test_match_outcome_and_persistence(client, test_db, user, enqueued):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    res = service.process_job(
        test_db, job.job_id, FakeVehicleAuthorityProvider()
    )
    assert res.action == "COMPLETED"

    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert (job.status, job.outcome, job.mismatched_fields) == (
        "COMPLETED", "MATCH", None,
    )
    assert job.completed_at is not None

    _, headers = login(client, test_db, "g@vvj.test", "government")
    r = client.get(
        f"/vehicle-verification-jobs/{job.job_id}", headers=headers
    )
    assert r.json()["outcome"] == "MATCH"
    assert r.json()["mismatched_fields"] == []
    assert "Secret Owner Name" not in r.text
    assert audit_actions(test_db) == [
        "VEHICLE_VERIFICATION_JOB_CREATED",
        "VEHICLE_VERIFICATION_JOB_STARTED",
        "VEHICLE_VERIFICATION_JOB_COMPLETED",
    ]


def test_match_never_touches_government_verification(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    service.process_job(test_db, job.job_id, FakeVehicleAuthorityProvider())
    test_db.expire_all()
    asset = test_db.query(AssetRegistry).one()
    assert asset.government_verification == "NOT_VERIFIED"
    assert test_db.query(GovernmentVerification).count() == 0


def test_match_is_case_and_whitespace_insensitive(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    provider = FakeVehicleAuthorityProvider(
        records={
            "VVJVIN0001": VehicleAuthorityRecord(
                vin=" vvjvin0001 ",
                registration_number="gt-vvj-1",
                chassis_number="chassis0001",
                engine_number="ENGINE0001",
            )
        }
    )
    service.process_job(test_db, job.job_id, provider)
    assert service.get_job(test_db, job.job_id).outcome == "MATCH"


def test_mismatch_outcome(test_db, user):
    asset = make_asset(test_db, vin="X1-FAKE-MISMATCH")
    job = new_job(test_db, asset, user)
    service.process_job(
        test_db, job.job_id, get_vehicle_authority_provider("fake")
    )
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert job.status == "COMPLETED"
    assert job.outcome == "MISMATCH"
    assert job.mismatched_fields == "CHASSIS_NUMBER"


def test_record_not_found_is_mismatch(test_db, user):
    asset = make_asset(test_db, vin="X1-FAKE-NOTFOUND")
    job = new_job(test_db, asset, user)
    service.process_job(
        test_db, job.job_id, get_vehicle_authority_provider("fake")
    )
    job = service.get_job(test_db, job.job_id)
    assert job.outcome == "MISMATCH"
    assert job.mismatched_fields == "RECORD_NOT_FOUND"


def test_only_fake_provider_available():
    assert get_vehicle_authority_provider("fake").name == "FAKE"
    with pytest.raises(ValueError):
        get_vehicle_authority_provider("dvla")


def test_provider_unavailable_retries_then_fails(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    provider = FakeVehicleAuthorityProvider(
        errors=[ProviderUnavailableError("secret provider text")] * 3
    )

    for attempt in (1, 2):
        res = service.process_job(test_db, job.job_id, provider)
        assert (res.action, res.attempt_count) == ("RETRY", attempt)
        test_db.expire_all()
        job = service.get_job(test_db, job.job_id)
        assert job.status == "PENDING"
        assert job.last_error_code == "PROVIDER_UNAVAILABLE"
        assert job.outcome is None

    res = service.process_job(test_db, job.job_id, provider)
    assert res.action == "FAILED"
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert job.status == "FAILED"
    assert job.attempt_count == 3
    assert job.last_error_code == "PROVIDER_UNAVAILABLE"

    # Terminal: no further changes or audit events.
    before = audit_actions(test_db)
    assert service.process_job(test_db, job.job_id, provider).action == "NOOP"
    assert audit_actions(test_db) == before
    assert provider.calls == 3
    assert "secret provider text" not in repr(
        [e.audit_metadata for e in test_db.query(AuditEvent).all()]
    )


def test_retry_then_success(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    provider = FakeVehicleAuthorityProvider(
        errors=[ProviderUnavailableError()]
    )
    assert service.process_job(test_db, job.job_id, provider).action == "RETRY"
    assert (
        service.process_job(test_db, job.job_id, provider).action
        == "COMPLETED"
    )
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert (job.status, job.outcome, job.attempt_count) == (
        "COMPLETED", "MATCH", 2,
    )
    assert audit_actions(test_db).count(
        "VEHICLE_VERIFICATION_JOB_RETRY_SCHEDULED"
    ) == 1


@pytest.mark.parametrize(
    "error,code",
    [
        (ProviderPermanentError("raw text"), "PROVIDER_ERROR"),
        (RuntimeError("raw text"), "PROVIDER_UNEXPECTED_ERROR"),
    ],
)
def test_permanent_errors_fail_immediately(test_db, user, error, code):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    res = service.process_job(
        test_db, job.job_id, FakeVehicleAuthorityProvider(errors=[error])
    )
    assert res.action == "FAILED"
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert (job.status, job.last_error_code) == ("FAILED", code)
    assert "raw text" not in repr(
        [e.audit_metadata for e in test_db.query(AuditEvent).all()]
    )


def test_duplicate_delivery_does_not_duplicate(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    provider = FakeVehicleAuthorityProvider()
    assert (
        service.process_job(test_db, job.job_id, provider).action
        == "COMPLETED"
    )
    snapshot = audit_actions(test_db)
    assert service.process_job(test_db, job.job_id, provider).action == "NOOP"
    assert provider.calls == 1
    assert audit_actions(test_db) == snapshot
    assert snapshot.count("VEHICLE_VERIFICATION_JOB_COMPLETED") == 1


def test_in_progress_job_with_live_lease_not_claimed(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    assert service._claim(test_db, job.job_id, service._now()) is not None
    # Second claim (duplicate delivery) is refused while lease is live.
    assert service._claim(test_db, job.job_id, service._now()) is None
    provider = FakeVehicleAuthorityProvider()
    assert service.process_job(test_db, job.job_id, provider).action == "NOOP"
    assert provider.calls == 0


def test_stale_lease_recovered(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    service._claim(test_db, job.job_id, service._now())

    # Simulate a crashed worker: lease expired.
    job = service.get_job(test_db, job.job_id)
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    test_db.commit()

    res = service.process_job(
        test_db, job.job_id, FakeVehicleAuthorityProvider()
    )
    assert res.action == "COMPLETED"
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert job.attempt_count == 2
    assert "VEHICLE_VERIFICATION_JOB_LEASE_RECOVERED" in audit_actions(test_db)


def test_stale_worker_cannot_overwrite_after_recovery(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    attempt1, _ = service._claim(test_db, job.job_id, service._now())

    job = service.get_job(test_db, job.job_id)
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    test_db.commit()
    service._claim(test_db, job.job_id, service._now())  # attempt 2

    applied = service._finish_failed(test_db, job.job_id, attempt1, "X")
    assert applied is False
    test_db.expire_all()
    assert service.get_job(test_db, job.job_id).status == "IN_PROGRESS"


def test_stale_job_with_exhausted_attempts_fails(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    job.status = "IN_PROGRESS"
    job.attempt_count = service.MAX_ATTEMPTS
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    test_db.commit()

    provider = FakeVehicleAuthorityProvider()
    assert service.process_job(test_db, job.job_id, provider).action == "NOOP"
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert job.status == "FAILED"
    assert job.last_error_code == "LEASE_EXPIRED_MAX_ATTEMPTS"
    assert provider.calls == 0


def test_provider_not_called_inside_open_transaction(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    seen = {}

    class Probe(FakeVehicleAuthorityProvider):
        def lookup(self, **kw):
            seen["in_transaction"] = test_db.in_transaction()
            return super().lookup(**kw)

    service.process_job(test_db, job.job_id, Probe())
    assert seen["in_transaction"] is False


def test_vehicle_missing_at_processing_fails(test_db, user):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)
    test_db.query(Vehicle).delete()
    test_db.commit()
    res = service.process_job(
        test_db, job.job_id, FakeVehicleAuthorityProvider()
    )
    assert res.action == "FAILED"
    assert (
        service.get_job(test_db, job.job_id).last_error_code
        == "VEHICLE_NOT_FOUND"
    )


def test_audit_event_rolled_back_with_state_change(test_db, user, monkeypatch):
    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)

    def boom(*a, **k):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(service, "record_audit_event", boom)
    with pytest.raises(RuntimeError):
        service._claim(test_db, job.job_id, service._now())
    test_db.rollback()
    test_db.expire_all()
    job = service.get_job(test_db, job.job_id)
    assert (job.status, job.attempt_count) == ("PENDING", 0)


# ---------- worker task ----------


def test_worker_task_runs_with_fake_provider(
    test_db, user, monkeypatch
):
    from app.worker import tasks

    asset = make_asset(test_db)
    job = new_job(test_db, asset, user)

    import app.database.database as dbmod

    monkeypatch.setattr(dbmod, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(test_db, "close", lambda: None)

    assert (
        tasks.process_vehicle_verification_job.apply(args=[job.job_id]).get()
        == "COMPLETED"
    )
    # Duplicate delivery is a no-op.
    assert (
        tasks.process_vehicle_verification_job.apply(args=[job.job_id]).get()
        == "NOOP"
    )
    assert service.get_job(test_db, job.job_id).outcome == "MATCH"
