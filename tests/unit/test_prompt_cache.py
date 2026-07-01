from autograde_llm.cached import CachedLLMClient, prompt_key
from autograde_llm.client import Backend, CompletionRequest, CompletionResult, LLMClient


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.ttls[key] = ttl


class CountingClient(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(
            text=f"completion-{self.calls}", model=request.model, backend=Backend.LOCAL,
            input_tokens=10, output_tokens=5,
        )


def _req(**overrides) -> CompletionRequest:
    base = dict(
        system="grade strictly", prompt="student answer", model="m",
        cache_prefix="rubric-v1|q1",
    )
    base.update(overrides)
    return CompletionRequest(**base)


def test_second_identical_call_hits_cache() -> None:
    inner = CountingClient()
    client = CachedLLMClient(inner, redis_client=FakeRedis())

    first = client.complete(_req())
    second = client.complete(_req())

    assert inner.calls == 1
    assert not first.cache_hit and second.cache_hit
    assert second.text == first.text


def test_key_varies_by_each_component() -> None:
    base = prompt_key(_req())
    assert prompt_key(_req(model="other")) != base
    assert prompt_key(_req(system="lenient")) != base
    assert prompt_key(_req(cache_prefix="rubric-v2|q1")) != base
    assert prompt_key(_req(prompt="different answer")) != base
    assert prompt_key(_req()) == base


def test_ttl_applied() -> None:
    redis = FakeRedis()
    client = CachedLLMClient(CountingClient(), redis_client=redis, ttl_s=1234)
    client.complete(_req())
    assert list(redis.ttls.values()) == [1234]
