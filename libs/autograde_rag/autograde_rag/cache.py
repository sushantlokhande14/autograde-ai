"""Redis JSON cache helpers (retrieval keyspace, design spec §7.4)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

import redis

from autograde_core.config import get_settings

RETRIEVAL_TTL_S = 3600  # 1h


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def retrieval_key(
    assignment_id: str,
    question_id: str,
    artifact_type: str,
    top_k: int,
    query_hint: str,
    include_reference: bool,
) -> str:
    digest = hashlib.sha256(
        f"{assignment_id}|{question_id}|{artifact_type}|{top_k}|{query_hint}|{include_reference}".encode()
    ).hexdigest()
    return f"retrieval:{digest}"


def cache_get(key: str, client: redis.Redis | None = None) -> Any | None:
    client = client or get_redis()
    raw = client.get(key)
    return json.loads(raw) if raw else None


def cache_set(key: str, value: Any, ttl_s: int, client: redis.Redis | None = None) -> None:
    client = client or get_redis()
    client.set(key, json.dumps(value, default=str), ex=ttl_s)
