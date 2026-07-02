"""LLM call auditing: every completion leaves a durable trail.

Wraps any LLMClient. Each call writes a ``grading.llm_calls`` row and stores
the full request/response JSON in MinIO ``llm-payloads/<llm_call_id>/`` — the
links that let an instructor go grade → llm_call → exact prompt in three
clicks. Auditing failures never fail the completion; they log and continue
(fail loud, fail isolated).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import structlog

from autograde_llm.client import CompletionRequest, CompletionResult, LLMClient

log = structlog.get_logger()


class AuditedLLMClient(LLMClient):
    """Decorator: persist llm_calls + payloads around the inner client."""

    def __init__(self, inner: LLMClient, grader: str) -> None:
        self.inner = inner
        self.grader = grader

    def complete(self, request: CompletionRequest) -> CompletionResult:
        result = self.inner.complete(request)
        # Always mint a fresh audit id: a prompt-cache hit replays the original
        # completion, whose llm_call_id already has an audit row — reusing it
        # collides on the primary key and loses cache-hit accounting.
        call_id = uuid4()
        result.llm_call_id = str(call_id)
        try:
            self._persist(call_id, request, result)
        except Exception as exc:  # noqa: BLE001 — audit must not break grading
            log.error("llm_audit_failed", grader=self.grader, error=str(exc))
        return result

    def _persist(self, call_id: UUID, request: CompletionRequest, result: CompletionResult) -> None:
        from autograde_core import storage
        from autograde_db.models import LlmCall
        from autograde_db.session import session_scope

        req_ref = f"{call_id}/request.json"
        resp_ref = f"{call_id}/response.json"
        storage.put_json("llm-payloads", req_ref, request.model_dump(mode="json"))
        storage.put_json("llm-payloads", resp_ref, result.model_dump(mode="json"))

        with session_scope() as session:
            session.add(
                LlmCall(
                    id=call_id,
                    grader=self.grader,
                    model=result.model,
                    backend=result.backend.value,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cache_hit=result.cache_hit,
                    latency_ms=result.latency_ms,
                    cost_usd=result.cost_usd,
                    request_payload_ref=req_ref,
                    response_payload_ref=resp_ref,
                )
            )


def grading_client(grader: str) -> LLMClient:
    """The standard grader stack: Ollama → prompt cache → audit.

    Cache hits are audited too (cache_hit=True rows) — that is the data behind
    the prefix-cache-hit-rate metric in Phase 6.
    """
    from autograde_llm.cached import CachedLLMClient
    from autograde_llm.ollama_backend import OllamaClient

    return AuditedLLMClient(CachedLLMClient(OllamaClient()), grader=grader)
