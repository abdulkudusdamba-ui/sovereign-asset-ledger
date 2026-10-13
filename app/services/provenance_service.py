import hashlib
import hmac
import json
import secrets
from datetime import timezone

from sqlalchemy.orm import Session

from app.blockchain.provider import BlockchainProvider, get_blockchain_provider
from app.core.config import settings
from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.models.provenance_commitment import (
    ProvenanceAnchorAttempt,
    ProvenanceCommitment,
)


COMMITMENT_FORMAT_VERSION = 1


def _parse_snapshot(value: str | None):
    if value is None:
        return None
    return json.loads(value)


def canonical_event_document(event: AuditEvent, sal_id: str | None) -> dict:
    """Return the explicitly allow-listed, versioned event commitment document."""
    occurred_at = event.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    occurred_at = occurred_at.astimezone(timezone.utc).isoformat()

    before_data = _parse_snapshot(event.before_data)
    after_data = _parse_snapshot(event.after_data)
    version = 1
    if isinstance(after_data, dict):
        candidate = after_data.get("version")
        if (
            isinstance(candidate, int)
            and not isinstance(candidate, bool)
            and candidate > 0
        ):
            version = candidate

    return {
        "format_version": COMMITMENT_FORMAT_VERSION,
        "event_id": event.event_id,
        "asset_id": sal_id,
        "passport_id": event.passport_id,
        "record_version": version,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "occurred_at": occurred_at,
        "result": event.result,
        "before_data": before_data,
        "after_data": after_data,
    }


def canonicalize(document: dict) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def calculate_commitment(canonical_document: dict, nonce: str) -> str:
    digest = hashlib.sha256()
    digest.update(b"SAL-PROVENANCE-COMMITMENT-v1\x00")
    digest.update(bytes.fromhex(nonce))
    digest.update(canonicalize(canonical_document))
    return digest.hexdigest()


def _signing_key() -> bytes | None:
    configured_key = settings.SAL_PROVENANCE_SIGNING_KEY
    return configured_key.encode("utf-8") if configured_key else None


def _signature_message(commitment_id: str, commitment_hash: str) -> bytes:
    return f"SAL-PROVENANCE-SIGNATURE-v1:{commitment_id}:{commitment_hash}".encode(
        "utf-8"
    )


def _sign(commitment_id: str, commitment_hash: str) -> tuple[str | None, str | None]:
    key = _signing_key()
    if key is None:
        return None, None
    signature = hmac.new(
        key,
        _signature_message(commitment_id, commitment_hash),
        hashlib.sha256,
    ).hexdigest()
    return settings.SAL_PROVENANCE_SIGNER_KEY_ID, signature


def _signature_valid(commitment: ProvenanceCommitment) -> bool | None:
    key = _signing_key()
    if not commitment.signature or not commitment.signer_key_id or key is None:
        return None
    if commitment.signer_key_id != settings.SAL_PROVENANCE_SIGNER_KEY_ID:
        return None
    expected = hmac.new(
        key,
        _signature_message(commitment.commitment_id, commitment.commitment_hash),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, commitment.signature)


def create_commitment(db: Session, event: AuditEvent) -> ProvenanceCommitment:
    existing = (
        db.query(ProvenanceCommitment)
        .filter(ProvenanceCommitment.event_id == event.event_id)
        .first()
    )
    if existing:
        return existing

    asset = None
    if event.asset_registry_id is not None:
        asset = (
            db.query(AssetRegistry)
            .filter(AssetRegistry.id == event.asset_registry_id)
            .first()
        )
    sal_id = asset.sal_id if asset else None
    document = canonical_event_document(event, sal_id)
    nonce = secrets.token_hex(32)
    commitment_id = f"SAL-PROV-{secrets.token_hex(8).upper()}"
    commitment_hash = calculate_commitment(document, nonce)
    signer_key_id, signature = _sign(commitment_id, commitment_hash)

    previous = None
    if event.asset_registry_id is not None:
        previous = (
            db.query(ProvenanceCommitment)
            .filter(
                ProvenanceCommitment.asset_registry_id == event.asset_registry_id
            )
            .order_by(ProvenanceCommitment.id.desc())
            .first()
        )

    commitment = ProvenanceCommitment(
        commitment_id=commitment_id,
        event_id=event.event_id,
        asset_registry_id=event.asset_registry_id,
        passport_id=event.passport_id,
        record_version=document["record_version"],
        format_version=COMMITMENT_FORMAT_VERSION,
        previous_commitment_id=previous.commitment_id if previous else None,
        commitment_hash=commitment_hash,
        nonce=nonce,
        signature=signature,
        signer_key_id=signer_key_id,
        ledger_provider="mock-ledger",
        network_id="sal-mocknet-v1",
        anchor_status="PENDING",
    )
    db.add(commitment)
    db.flush()
    return commitment


def process_anchor(
    db: Session,
    commitment: ProvenanceCommitment,
    provider: BlockchainProvider | None = None,
) -> ProvenanceCommitment:
    if commitment.anchor_status == "CONFIRMED":
        return commitment

    provider = provider or get_blockchain_provider()
    commitment.anchor_attempts += 1
    try:
        receipt = provider.anchor(commitment.commitment_hash)
        commitment.ledger_provider = receipt.provider
        commitment.network_id = receipt.network_id
        commitment.anchor_reference = receipt.reference
        commitment.anchor_status = "CONFIRMED"
        commitment.last_anchor_error = None
        attempt = ProvenanceAnchorAttempt(
            commitment_id=commitment.id,
            provider=receipt.provider,
            status="CONFIRMED",
            anchor_reference=receipt.reference,
        )
    except Exception as exc:
        commitment.anchor_status = "FAILED"
        commitment.anchor_reference = None
        commitment.last_anchor_error = type(exc).__name__
        attempt = ProvenanceAnchorAttempt(
            commitment_id=commitment.id,
            provider=provider.provider_name,
            status="FAILED",
            error_code=type(exc).__name__,
        )
    db.add(attempt)
    db.flush()
    return commitment


def verify_commitment(
    db: Session,
    commitment: ProvenanceCommitment,
    provider: BlockchainProvider | None = None,
) -> dict:
    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.event_id == commitment.event_id)
        .first()
    )
    asset = None
    if event and event.asset_registry_id is not None:
        asset = (
            db.query(AssetRegistry)
            .filter(AssetRegistry.id == event.asset_registry_id)
            .first()
        )
    digest_matches = False
    if event:
        try:
            document = canonical_event_document(event, asset.sal_id if asset else None)
            digest_matches = hmac.compare_digest(
                calculate_commitment(document, commitment.nonce),
                commitment.commitment_hash,
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            digest_matches = False

    provider = provider or get_blockchain_provider()
    try:
        anchor_matches = (
            commitment.anchor_status == "CONFIRMED"
            and provider.provider_name == commitment.ledger_provider
            and provider.network_id == commitment.network_id
            and provider.verify(
                commitment.commitment_hash,
                commitment.anchor_reference or "",
            )
        )
    except Exception:
        anchor_matches = False
    signature_valid = _signature_valid(commitment)
    return {
        "commitment_id": commitment.commitment_id,
        "commitment_valid": digest_matches,
        "signature_valid": signature_valid,
        "anchor_valid": anchor_matches,
        "verified": (
            digest_matches
            and anchor_matches
            and signature_valid is not False
        ),
        "legal_ownership_verified": False,
    }


def commitment_metadata(commitment: ProvenanceCommitment) -> dict:
    return {
        "commitment_id": commitment.commitment_id,
        "event_id": commitment.event_id,
        "asset_registry_id": commitment.asset_registry_id,
        "passport_id": commitment.passport_id,
        "record_version": commitment.record_version,
        "format_version": commitment.format_version,
        "previous_commitment_id": commitment.previous_commitment_id,
        "commitment_hash": commitment.commitment_hash,
        "nonce": commitment.nonce,
        "signature": commitment.signature,
        "signer_key_id": commitment.signer_key_id,
        "created_at": commitment.created_at,
        "ledger_provider": commitment.ledger_provider,
        "network_id": commitment.network_id,
        "anchor_status": commitment.anchor_status,
        "anchor_reference": commitment.anchor_reference,
        "anchor_attempts": commitment.anchor_attempts,
        "last_anchor_error": commitment.last_anchor_error,
        "legal_ownership_verified": False,
    }
