"""Unified LLM client interface.

One surface over the local model server (Ollama/vLLM) and the optional hosted
backends (Anthropic, OpenAI). Phase 0 defines the interface and the request /
response shapes; concrete backends are implemented in Phase 3 when the first
graders come online.
"""

from autograde_llm.client import Backend, CompletionRequest, CompletionResult, LLMClient
from autograde_llm.ollama_backend import OllamaClient

__all__ = ["Backend", "CompletionRequest", "CompletionResult", "LLMClient", "OllamaClient"]
