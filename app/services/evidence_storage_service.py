from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


class EvidenceStorageError(Exception):
    """Base exception for Evidence Storage failures."""


class EvidenceFingerprintMismatchError(EvidenceStorageError):
    """Raised when supplied and calculated fingerprints differ."""


class InvalidEvidenceIdentifierError(EvidenceStorageError):
    """Raised when an evidence identifier is unsafe."""


class EvidenceAlreadyExistsError(EvidenceStorageError):
    """Raised when evidence already exists and would be overwritten."""


@dataclass(frozen=True)
class StoredEvidence:
    evidence_id: str
    storage_path: str
    size_bytes: int
    fingerprint_sha256: str


class LocalEvidenceStorage:
    """
    Local development storage backend for SAL Evidence.

    Evidence objects are immutable once stored.

    This service intentionally has no FastAPI or SQLAlchemy dependency.
    It can later be replaced by an encrypted object-storage backend
    without changing the Evidence API contract.
    """

    SAFE_EVIDENCE_ID = re.compile(r"^[A-Za-z0-9_-]+$")

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_evidence_id(self, evidence_id: str) -> None:
        if not evidence_id or not self.SAFE_EVIDENCE_ID.fullmatch(evidence_id):
            raise InvalidEvidenceIdentifierError(
                "Invalid evidence_id"
            )

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def store(
        self,
        evidence_id: str,
        content: bytes,
        expected_fingerprint_sha256: str | None = None,
    ) -> StoredEvidence:
        self._validate_evidence_id(evidence_id)

        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")

        calculated_fingerprint = self.calculate_sha256(content)

        if expected_fingerprint_sha256 is not None:
            expected = expected_fingerprint_sha256.strip().lower()

            if expected != calculated_fingerprint:
                raise EvidenceFingerprintMismatchError(
                    "Evidence SHA-256 fingerprint does not match file content"
                )

        final_path = self.root / f"{evidence_id}.bin"

        if final_path.exists():
            raise EvidenceAlreadyExistsError(
                "Evidence already exists and cannot be overwritten"
            )

        fd, temporary_path = tempfile.mkstemp(
            prefix=f".{evidence_id}.",
            suffix=".tmp",
            dir=self.root,
        )

        try:
            with os.fdopen(fd, "wb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            # Atomic creation without permitting replacement of existing evidence.
            try:
                os.link(temporary_path, final_path)
            except FileExistsError as exc:
                raise EvidenceAlreadyExistsError(
                    "Evidence already exists and cannot be overwritten"
                ) from exc
            finally:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass

        except Exception:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            raise

        return StoredEvidence(
            evidence_id=evidence_id,
            storage_path=str(final_path),
            size_bytes=len(content),
            fingerprint_sha256=calculated_fingerprint,
        )

    def exists(self, evidence_id: str) -> bool:
        self._validate_evidence_id(evidence_id)
        return (self.root / f"{evidence_id}.bin").is_file()

    def read(self, evidence_id: str) -> bytes:
        """
        Read an immutable evidence object from local storage.

        This method performs identifier validation before constructing
        the storage path and raises EvidenceStorageError when the
        evidence object does not exist or cannot be read.
        """
        self._validate_evidence_id(evidence_id)

        path = self.root / f"{evidence_id}.bin"

        if not path.is_file():
            raise EvidenceStorageError(
                "Evidence file not found"
            )

        try:
            return path.read_bytes()
        except OSError as exc:
            raise EvidenceStorageError(
                "Evidence file could not be read"
            ) from exc

    def verify_integrity(
        self,
        evidence_id: str,
        expected_fingerprint_sha256: str,
    ) -> tuple[str, bool]:
        """
        Recalculate the stored evidence SHA-256 fingerprint and compare
        it with the fingerprint recorded by SAL.
        """
        if not expected_fingerprint_sha256:
            raise EvidenceStorageError(
                "Evidence does not have a recorded SHA-256 fingerprint"
            )

        content = self.read(evidence_id)
        calculated_fingerprint = self.calculate_sha256(content)

        return (
            calculated_fingerprint,
            calculated_fingerprint == expected_fingerprint_sha256.strip().lower(),
        )

    def delete(self, evidence_id: str) -> None:
        """
        Delete a stored evidence object.

        This is intended primarily for compensating cleanup when
        database persistence fails after successful file storage.
        """
        self._validate_evidence_id(evidence_id)

        path = self.root / f"{evidence_id}.bin"

        try:
            path.unlink()
        except FileNotFoundError:
            return
