"""MinIO object storage helpers.

Thin wrapper over the MinIO client that applies the bucket prefix, ensures the
pipeline's buckets exist, and offers JSON/bytes get/put. Buckets are immutable
after write (PROJECT_PLAN §7.3); we never overwrite silently in higher layers.
"""

from __future__ import annotations

import io
import json
from typing import Any

from minio import Minio

from autograde_core.config import get_settings

# Logical bucket names (prefix applied at runtime).
LOGICAL_BUCKETS: tuple[str, ...] = (
    "raw-uploads",
    "raw-submissions",
    "normalized-artifacts",
    "sandbox-logs",
    "llm-payloads",
    "exports",
)


def get_minio() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )


def bucket_name(logical: str) -> str:
    """Apply the configured prefix, e.g. ``raw-uploads`` -> ``autograde-raw-uploads``."""
    prefix = get_settings().minio_bucket_prefix
    return logical if logical.startswith(prefix) else f"{prefix}{logical}"


def ensure_buckets(client: Minio | None = None) -> list[str]:
    """Create any missing pipeline buckets. Idempotent."""
    client = client or get_minio()
    created: list[str] = []
    for logical in LOGICAL_BUCKETS:
        name = bucket_name(logical)
        if not client.bucket_exists(name):
            client.make_bucket(name)
            created.append(name)
    return created


def put_bytes(logical: str, key: str, data: bytes, content_type: str, client: Minio | None = None) -> str:
    client = client or get_minio()
    name = bucket_name(logical)
    client.put_object(name, key, io.BytesIO(data), length=len(data), content_type=content_type)
    return key


def get_bytes(logical: str, key: str, client: Minio | None = None) -> bytes:
    client = client or get_minio()
    response = client.get_object(bucket_name(logical), key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def put_json(logical: str, key: str, obj: Any, client: Minio | None = None) -> str:
    data = json.dumps(obj, default=str).encode()
    return put_bytes(logical, key, data, content_type="application/json", client=client)


def get_json(logical: str, key: str, client: Minio | None = None) -> Any:
    return json.loads(get_bytes(logical, key, client=client))
