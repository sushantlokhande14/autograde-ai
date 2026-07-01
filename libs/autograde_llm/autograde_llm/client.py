"""LLM client interface and value types.

The concrete call path (prompt caching, token accounting into grading.llm_calls,
OTel spans) is built in Phase 3. Here we lock the shapes so graders can be
written against a stable interface.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Backend(str, Enum):
    LOCAL = "local"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class CompletionRequest(BaseModel):
    system: str
    prompt: str
    model: str
    max_tokens: int = 1024
    temperature: float = 0.0
    # Stable prefix (rubric + reference) used as the prompt-cache key.
    cache_prefix: str | None = None


class CompletionResult(BaseModel):
    text: str
    model: str
    backend: Backend
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit: bool = False
    latency_ms: int = 0
    cost_usd: float = 0.0
    llm_call_id: str | None = Field(default=None)


class LLMClient:
    """Interface every backend implements. Phase 3 provides the implementations."""

    def complete(self, request: CompletionRequest) -> CompletionResult:  # pragma: no cover
        raise NotImplementedError("LLM backends are implemented in Phase 3.")
