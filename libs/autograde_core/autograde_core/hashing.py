"""Deterministic identifiers.

Two goals: (1) keep real identity out of the grading pipeline — a student is
only ever a `student_hash`; (2) make ingestion idempotent — the same input
always derives the same submission and artifact ids, so Kafka replay never
double-creates rows.
"""

from __future__ import annotations

import hashlib
import hmac
from uuid import NAMESPACE_URL, UUID, uuid5

from autograde_core.config import get_settings

_ID_NAMESPACE = uuid5(NAMESPACE_URL, "autograde-ai")


def student_hash(assignment_id: str, canvas_id: str, secret: str | None = None) -> str:
    """HMAC-SHA256 of the identity, keyed by the deployment secret."""
    key = (secret if secret is not None else get_settings().student_hash_secret).encode()
    return hmac.new(key, f"{assignment_id}:{canvas_id}".encode(), hashlib.sha256).hexdigest()


def submission_id_for(assignment_id: str, student_hash_value: str) -> UUID:
    """Stable submission id from assignment + student hash."""
    return uuid5(_ID_NAMESPACE, f"submission:{assignment_id}:{student_hash_value}")


def artifact_id_for(submission_id: UUID, source_file: str, sha256: str) -> UUID:
    """Stable artifact id from its submission, source path, and content hash."""
    return uuid5(_ID_NAMESPACE, f"artifact:{submission_id}:{source_file}:{sha256}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
