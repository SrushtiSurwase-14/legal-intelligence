"""LLM access behind a tiny interface so it can be swapped, faked in tests, or fail on purpose."""
from __future__ import annotations

from typing import Callable, Protocol

from .config import Settings


class LLMUnavailable(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, prompt: str) -> str: ...


class NullLLM:
    name = "none"

    def complete(self, system: str, prompt: str) -> str:
        raise LLMUnavailable("No LLM provider configured (LI_LLM_PROVIDER=none).")


class FailingLLM:
    name = "failing"

    def complete(self, system: str, prompt: str) -> str:
        raise LLMUnavailable("simulated LLM outage")


class FakeLLM:
    """Test double: returns a fixed string or calls a function."""
    name = "fake"

    def __init__(self, response: str | Callable[[str, str], str]):
        self.response, self.calls = response, []

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        return self.response(system, prompt) if callable(self.response) else self.response


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        try:
            import anthropic
        except ImportError as e:
            raise LLMUnavailable("anthropic package not installed (pip install anthropic)") from e
        self._client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        self.model = model

    def complete(self, system: str, prompt: str) -> str:
        try:
            r = self._client.messages.create(model=self.model, max_tokens=1500, temperature=0, system=system,
                                             messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        except Exception as e:  # noqa: BLE001 - any SDK/network error means "model unavailable"
            raise LLMUnavailable(f"{e.__class__.__name__}: {str(e)[:200]}") from e


def build_llm(settings: Settings) -> LLMClient:
    if settings.simulate_failure == "llm":
        return FailingLLM()
    if settings.llm_provider == "anthropic":
        if not settings.llm_api_key:
            return NullLLM()
        try:
            return AnthropicLLM(settings.llm_api_key, settings.llm_model)
        except LLMUnavailable:
            return NullLLM()
    return NullLLM()
