"""Ollama backend: the first concrete LLMClient.

Pulled forward from Phase 3 for the QuestionMapper. Token accounting comes from
Ollama's eval counts; cost is 0 (local). Payload persistence into
grading.llm_calls / MinIO llm-payloads arrives with the Phase 3 audit work.
"""

from __future__ import annotations

import time
from uuid import uuid4

import httpx

from autograde_core.config import get_settings
from autograde_llm.client import Backend, CompletionRequest, CompletionResult, LLMClient


class OllamaClient(LLMClient):
    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        self.base_url = (base_url or get_settings().ollama_url).rstrip("/")
        self.timeout = timeout

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started = time.monotonic()
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": request.model,
                "system": request.system,
                "prompt": request.prompt,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        return CompletionResult(
            text=body.get("response", ""),
            model=request.model,
            backend=Backend.LOCAL,
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
            cache_hit=False,
            latency_ms=int((time.monotonic() - started) * 1000),
            cost_usd=0.0,
            llm_call_id=str(uuid4()),
        )
