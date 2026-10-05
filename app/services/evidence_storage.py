from __future__ import annotations

import os
from pathlib import Path

from app.services.evidence_storage_service import LocalEvidenceStorage


DEFAULT_EVIDENCE_STORAGE_ROOT = (
    Path(__file__).resolve().parents[2] / "storage" / "evidence"
)


def get_evidence_storage_root() -> Path:
    """
    Return the configured local Evidence storage root.

    The environment variable allows deployment-specific storage
    configuration without changing application code.

    For development, the default is:
        <project-root>/storage/evidence
    """

    configured_root = os.getenv(
        "SAL_EVIDENCE_STORAGE_ROOT"
    )

    if configured_root:
        return Path(configured_root).expanduser().resolve()

    return DEFAULT_EVIDENCE_STORAGE_ROOT


def get_evidence_storage() -> LocalEvidenceStorage:
    """
    Return the active local Evidence storage backend.

    This factory is intentionally small so the application can later
    replace LocalEvidenceStorage with encrypted object storage without
    changing the Evidence router contract.
    """

    return LocalEvidenceStorage(
        root=get_evidence_storage_root()
    )
