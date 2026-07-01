"""Redis prompt cache wrapping any LLMClient.

Key per PROJECT_PLAN §7.4: ``prompt:<sha256(model, system, rubric_prefix,
prompt)>`` with a 24h TTL. Hits return the stored completion with
``cache_hit=True`` and near-zero latency — the mechanism behind the "95%+
prefix cache hit on shared rubric context" resume claim, measured for real in
Phase 6.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Protocol

from autograde_llm.client import CompletionRequest, CompletionResult, LLMClient

PROMPT_TTL_S = 24 * 3600


class _RedisLike(Protocol):
    def get(self, key: str) -> str | None: ...
    def setex(self, key: str, ttl: int, value: str) -> object: ...


def prompt_key(request: CompletionRequest) -> str:
    digest = hashlib.sha256(
        "|".join(
            [request.model, request.system, request.cache_prefix or "", request.prompt]
        ).encode()
    ).hexdigest()
    return f"prompt:{digest}"


def _default_redis() -> _RedisLike:
    import redis

    from autograde_core.config import get_settings

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


class CachedLLMClient(LLMClient):
    """Decorator: consult Redis before delegating to the inner backend."""

    def __init__(
        self,
        inner: LLMClient,
        redis_client: _RedisLike | None = None,
        ttl_s: int = PROMPT_TTL_S,
    ) -> None:
        self.inner = inner
        self.redis = redis_client or _default_redis()
        self.ttl_s = ttl_s

    def complete(self, request: CompletionRequest) -> CompletionResult:
        key = prompt_key(request)
        started = time.monotonic()
        raw = self.redis.get(key)
        if raw is not None:
            result = CompletionResult.model_validate(json.loads(raw))
            result.cache_hit = True
            result.latency_ms = int((time.monotonic() - started) * 1000)
            return result

        result = self.inner.complete(request)
        self.redis.setex(key, self.ttl_s, result.model_dump_json())
        return result
