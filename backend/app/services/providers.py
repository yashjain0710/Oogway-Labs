"""LLM provider abstraction. Swap models via env — no code changes.

Providers: ollama (local default/demo), anthropic, openai, mock (tests/demo
fallback when no keys and Ollama is down — clearly labelled, never silent).

Agent-SDK note (documented decision): the Anthropic Claude Agent SDK / Pi
Coding Agent are interactive coding agents, not server-side chat runtimes.
They are not embedded as a request-path dependency; instead this module
implements the same boundary (routing -> skill -> provider) with a clean
interface so a team can add an SDK-backed provider later. See architecture.md.
"""
import logging
import re
from dataclasses import dataclass

import httpx

from ..config import get_settings

log = logging.getLogger("lenny.llm")


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retriable: bool = False):
        super().__init__(message)
        self.retriable = retriable


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


class BaseProvider:
    name = "base"

    def generate(self, system: str, prompt: str) -> LLMResult:
        raise NotImplementedError


_SPECIAL = re.compile(r"<\|[^|>]*\|>")
_META_PH = re.compile(r"\[(end|assistant|system|user)\]")


def _clean_output(text: str) -> str:
    """Strip chat-template artifacts (phi3 family wraps output in <|ass_output|>…)."""
    text = _SPECIAL.sub(" ", text)
    text = _META_PH.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


class OllamaProvider(BaseProvider):
    name = "ollama"

    def generate(self, system: str, prompt: str) -> LLMResult:
        s = get_settings()
        # /api/chat (not /api/generate): reliably returns message.content across
        # model families, and passes the system role distinctly.
        url = s.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
        payload = {
            "model": s.OLLAMA_MODEL,
            "stream": False,
            "options": {"temperature": 0.3},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        try:
            r = httpx.post(url, json=payload, timeout=s.OLLAMA_TIMEOUT_S)
        except Exception as e:  # noqa: BLE001 (connection refused etc.)
            raise ProviderError(
                "Ollama is not reachable at %s. Start it with `ollama serve`, "
                "then `ollama pull %s`. Or set LLM_PROVIDER=anthropic with "
                "ANTHROPIC_API_KEY." % (s.OLLAMA_BASE_URL, s.OLLAMA_MODEL)
            ) from e
        if r.status_code == 404:
            raise ProviderError(
                "Ollama has no model named '%s'. Run `ollama pull %s` first." % (s.OLLAMA_MODEL, s.OLLAMA_MODEL)
            )
        if r.status_code >= 400:
            raise ProviderError(f"Ollama error {r.status_code}: {r.text[:300]}", retriable=True)
        try:
            body = r.json()
            msg = body.get("message") or {}
            text = _clean_output(msg.get("content", "") or body.get("response", ""))
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Ollama returned non-JSON output: {r.text[:300]}", retriable=True) from e
        if not text:
            raise ProviderError("Ollama returned an empty response.", retriable=True)
        log.info("llm.ollama ok model=%s chars=%d", s.OLLAMA_MODEL, len(text))
        return LLMResult(text=text, provider="ollama", model=s.OLLAMA_MODEL)


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def generate(self, system: str, prompt: str) -> LLMResult:
        s = get_settings()
        if not s.ANTHROPIC_API_KEY:
            raise ProviderError("ANTHROPIC_API_KEY is not set. Add it to .env to use the cloud provider.")
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": s.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": s.ANTHROPIC_MODEL, "max_tokens": 2048,
                      "system": system, "messages": [{"role": "user", "content": prompt}]},
                timeout=90,
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Anthropic request failed: {e}", retriable=True) from e
        if r.status_code >= 400:
            raise ProviderError(f"Anthropic error {r.status_code}: {r.text[:300]}", retriable=r.status_code >= 500)
        try:
            blocks = r.json().get("content", [])
            text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict)).strip()
        except Exception as e:  # noqa: BLE001
            raise ProviderError("Anthropic returned unreadable output.", retriable=True) from e
        return LLMResult(text=text, provider="anthropic", model=s.ANTHROPIC_MODEL)


class OpenAIProvider(BaseProvider):
    name = "openai"

    def generate(self, system: str, prompt: str) -> LLMResult:
        s = get_settings()
        if not s.OPENAI_API_KEY:
            raise ProviderError("OPENAI_API_KEY is not set. Add it to .env to use the cloud provider.")
        try:
            r = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"authorization": f"Bearer {s.OPENAI_API_KEY}"},
                json={"model": s.OPENAI_MODEL, "temperature": 0.3,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                timeout=90,
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"OpenAI request failed: {e}", retriable=True) from e
        if r.status_code >= 400:
            raise ProviderError(f"OpenAI error {r.status_code}: {r.text[:300]}", retriable=r.status_code >= 500)
        try:
            text = r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            raise ProviderError("OpenAI returned unreadable output.", retriable=True) from e
        return LLMResult(text=text, provider="openai", model=s.OPENAI_MODEL)


class MockProvider(BaseProvider):
    """Deterministic test/demo provider. Clearly labelled as mock."""
    name = "mock"

    def generate(self, system: str, prompt: str) -> LLMResult:
        head = prompt[:600].replace("\n", " ")
        return LLMResult(
            text=f"[mock:{get_settings().LLM_MODEL}] Grounded draft based on the retrieved context. Prompt starts: {head}…",
            provider="mock", model=get_settings().LLM_MODEL,
        )


def get_provider(name: str | None = None) -> BaseProvider:
    name = (name or get_settings().LLM_PROVIDER).lower()
    if name == "ollama":
        return OllamaProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "mock":
        return MockProvider()
    raise ProviderError(f"Unknown LLM_PROVIDER='{name}'. Use ollama | anthropic | openai | mock.")


def available_models() -> dict:
    s = get_settings()
    return {
        "active_provider": s.LLM_PROVIDER,
        "active_model": s.LLM_MODEL,
        "ollama": {"base_url": s.OLLAMA_BASE_URL, "model": s.OLLAMA_MODEL},
        "anthropic": {"model": s.ANTHROPIC_MODEL, "configured": bool(s.ANTHROPIC_API_KEY)},
        "openai": {"model": s.OPENAI_MODEL, "configured": bool(s.OPENAI_API_KEY)},
        "fallback_enabled": s.LLM_FALLBACK_ENABLED,
        "fallback_provider": s.LLM_FALLBACK_PROVIDER,
    }
