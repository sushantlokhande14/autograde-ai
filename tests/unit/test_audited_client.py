from autograde_llm.audited import AuditedLLMClient
from autograde_llm.client import Backend, CompletionRequest, CompletionResult, LLMClient


class ReplayClient(LLMClient):
    """Simulates a prompt-cache inner client: same llm_call_id on every call."""

    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult(
            text="cached", model="m", backend=Backend.LOCAL,
            cache_hit=True, llm_call_id="11111111-1111-1111-1111-111111111111",
        )


class RecordingAudit(AuditedLLMClient):
    def __init__(self, inner: LLMClient) -> None:
        super().__init__(inner, grader="T")
        self.persisted: list[str] = []

    def _persist(self, call_id, request, result) -> None:  # no DB in unit tests
        self.persisted.append(str(call_id))


def test_cache_hits_get_fresh_audit_ids() -> None:
    client = RecordingAudit(ReplayClient())
    req = CompletionRequest(system="s", prompt="p", model="m")
    first = client.complete(req)
    second = client.complete(req)
    assert first.llm_call_id != "11111111-1111-1111-1111-111111111111"
    assert first.llm_call_id != second.llm_call_id  # no PK collision
    assert client.persisted == [first.llm_call_id, second.llm_call_id]
