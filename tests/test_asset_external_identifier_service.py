from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.services.asset_external_identifier_service import (
    AssetExternalIdentifierConflictError,
    AssetRegistryNotFoundError,
    add_external_identifier,
    find_asset_by_external_identifier,
    get_external_identifier,
    get_external_identifiers,
    update_external_identifier_status,
)


def create_asset(test_db):
    asset = AssetRegistry(
        sal_id="SAL-TEST-EXT-001",
        asset_type="Vehicle",
        registry_id=1001,
        owner="SAL Test Owner",
        estimated_value=150000.0,
    )

    test_db.add(asset)
    test_db.commit()
    test_db.refresh(asset)

    return asset


def test_add_external_identifier_success(test_db):
    asset = create_asset(test_db)

    identifier = add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="dvla",
        identifier_type="rfid",
        identifier_value="dvla-rfid-001",
        source_reference="DVLA-TEST-REF-001",
    )

    test_db.commit()

    assert identifier.id is not None
    assert identifier.asset_registry_id == asset.id
    assert identifier.authority == "DVLA"
    assert identifier.identifier_type == "RFID"
    assert identifier.identifier_value == "DVLA-RFID-001"
    assert identifier.status == "ACTIVE"


def test_add_external_identifier_normalizes_values(test_db):
    asset = create_asset(test_db)

    identifier = add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="  dvla  ",
        identifier_type="  rfid ",
        identifier_value="  gh-123-rfid  ",
    )

    test_db.commit()

    assert identifier.authority == "DVLA"
    assert identifier.identifier_type == "RFID"
    assert identifier.identifier_value == "GH-123-RFID"


def test_duplicate_active_identifier_is_rejected(test_db):
    asset = create_asset(test_db)

    add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="DUPLICATE-001",
    )

    test_db.commit()

    try:
        add_external_identifier(
            test_db,
            asset_registry_id=asset.id,
            authority="dvla",
            identifier_type="rfid",
            identifier_value="duplicate-001",
        )
        assert False, "Expected duplicate identifier conflict"
    except AssetExternalIdentifierConflictError:
        pass


def test_missing_asset_is_rejected(test_db):
    try:
        add_external_identifier(
            test_db,
            asset_registry_id=999999,
            authority="DVLA",
            identifier_type="RFID",
            identifier_value="MISSING-ASSET-001",
        )
        assert False, "Expected missing asset error"
    except AssetRegistryNotFoundError:
        pass


def test_get_external_identifiers(test_db):
    asset = create_asset(test_db)

    add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="RFID-001",
    )

    add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="REGISTRATION",
        identifier_value="GT-TEST-001",
    )

    test_db.commit()

    identifiers = get_external_identifiers(
        test_db,
        asset_registry_id=asset.id,
    )

    assert len(identifiers) == 2
    assert identifiers[0].identifier_value == "RFID-001"
    assert identifiers[1].identifier_value == "GT-TEST-001"


def test_get_external_identifier(test_db):
    asset = create_asset(test_db)

    identifier = add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="LOOKUP-001",
    )

    test_db.commit()

    found = get_external_identifier(
        test_db,
        identifier_id=identifier.id,
    )

    assert found.id == identifier.id
    assert found.identifier_value == "LOOKUP-001"


def test_find_asset_by_external_identifier(test_db):
    asset = create_asset(test_db)

    add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="FIND-001",
    )

    test_db.commit()

    found_asset = find_asset_by_external_identifier(
        test_db,
        authority="dvla",
        identifier_type="rfid",
        identifier_value="find-001",
    )

    assert found_asset is not None
    assert found_asset.id == asset.id
    assert found_asset.sal_id == "SAL-TEST-EXT-001"


def test_find_asset_returns_none_for_unknown_identifier(test_db):
    result = find_asset_by_external_identifier(
        test_db,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="DOES-NOT-EXIST",
    )

    assert result is None


def test_update_external_identifier_status(test_db):
    asset = create_asset(test_db)

    identifier = add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="STATUS-001",
    )

    test_db.commit()

    updated = update_external_identifier_status(
        test_db,
        identifier_id=identifier.id,
        new_status="RETIRED",
        reason="Test retirement",
    )

    test_db.commit()

    assert updated.status == "RETIRED"


def test_external_identifier_operations_create_audit_events(test_db):
    asset = create_asset(test_db)

    identifier = add_external_identifier(
        test_db,
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="AUDIT-001",
        reason="Initial external identifier registration",
    )

    test_db.commit()

    update_external_identifier_status(
        test_db,
        identifier_id=identifier.id,
        new_status="RETIRED",
        reason="Retirement test",
    )

    test_db.commit()

    events = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.asset_registry_id == asset.id,
            AuditEvent.entity_type == "ASSET_EXTERNAL_IDENTIFIER",
        )
        .order_by(AuditEvent.id.asc())
        .all()
    )

    assert len(events) == 2

    assert events[0].action == "EXTERNAL_IDENTIFIER_CREATED"
    assert events[0].result == "SUCCESS"

    assert events[1].action == "EXTERNAL_IDENTIFIER_STATUS_CHANGED"
    assert events[1].result == "SUCCESS"
