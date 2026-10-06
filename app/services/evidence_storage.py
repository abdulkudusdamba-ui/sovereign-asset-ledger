from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings
from app.services.evidence_storage_service import LocalEvidenceStorage


DEFAULT_EVIDENCE_STORAGE_ROOT = (
    Path(__file__).resolve().parents[2] / "storage" / "evidence"
)


def get_evidence_storage_root() -> Path:
    """
    Return the configured local Evidence storage root.

    Evidence storage is resolved at call time so deployment-specific
    environment changes are respected by tests and by processes that
    intentionally configure storage before performing an operation.

    The centralized settings layer remains the source of the default.
    """

    configured_root = os.getenv(
        "SAL_EVIDENCE_STORAGE_ROOT"
    )

    if configured_root:
        return Path(configured_root).expanduser().resolve()

    configured_root = settings.SAL_EVIDENCE_STORAGE_ROOT

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
