import hashlib

import pytest

from app.services.evidence_storage_service import (
    EvidenceFingerprintMismatchError,
    InvalidEvidenceIdentifierError,
    LocalEvidenceStorage,
)


def test_storage_calculates_sha256_from_actual_content(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")
    content = b"SAL evidence integrity test"

    stored = storage.store(
        evidence_id="SAL-EVIDENCE-001",
        content=content,
    )

    expected = hashlib.sha256(content).hexdigest()

    assert stored.fingerprint_sha256 == expected
    assert stored.size_bytes == len(content)
    assert storage.exists("SAL-EVIDENCE-001")


def test_storage_accepts_matching_declared_fingerprint(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")
    content = b"Verified SAL evidence"
    fingerprint = hashlib.sha256(content).hexdigest().upper()

    stored = storage.store(
        evidence_id="SAL-EVIDENCE-002",
        content=content,
        expected_fingerprint_sha256=fingerprint,
    )

    assert stored.fingerprint_sha256 == fingerprint.lower()


def test_storage_rejects_mismatched_declared_fingerprint(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")
    content = b"Tamper detection test"

    with pytest.raises(EvidenceFingerprintMismatchError):
        storage.store(
            evidence_id="SAL-EVIDENCE-003",
            content=content,
            expected_fingerprint_sha256="a" * 64,
        )

    assert not storage.exists("SAL-EVIDENCE-003")


def test_storage_rejects_path_traversal_identifier(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")

    with pytest.raises(InvalidEvidenceIdentifierError):
        storage.store(
            evidence_id="../outside",
            content=b"unsafe",
        )


def test_storage_writes_exact_file_content(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")
    content = b"Exact SAL evidence bytes"

    stored = storage.store(
        evidence_id="SAL-EVIDENCE-004",
        content=content,
    )

    assert open(stored.storage_path, "rb").read() == content


def test_storage_creates_root_directory(tmp_path):
    root = tmp_path / "nested" / "evidence"
    storage = LocalEvidenceStorage(root)

    assert root.is_dir()
    assert storage.root == root.resolve()


def test_storage_rejects_overwrite_of_existing_evidence(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")

    original_content = b"Original SAL evidence"
    replacement_content = b"Replacement SAL evidence"

    storage.store(
        evidence_id="SAL-EVIDENCE-005",
        content=original_content,
    )

    with pytest.raises(Exception) as exc_info:
        storage.store(
            evidence_id="SAL-EVIDENCE-005",
            content=replacement_content,
        )

    assert "cannot be overwritten" in str(exc_info.value)

    stored_path = storage.root / "SAL-EVIDENCE-005.bin"
    assert stored_path.read_bytes() == original_content


def test_storage_duplicate_write_does_not_change_fingerprint(tmp_path):
    storage = LocalEvidenceStorage(tmp_path / "evidence")

    original_content = b"Immutable evidence bytes"
    original = storage.store(
        evidence_id="SAL-EVIDENCE-006",
        content=original_content,
    )

    with pytest.raises(Exception):
        storage.store(
            evidence_id="SAL-EVIDENCE-006",
            content=b"Different bytes",
        )

    assert storage.calculate_sha256(
        (storage.root / "SAL-EVIDENCE-006.bin").read_bytes()
    ) == original.fingerprint_sha256
