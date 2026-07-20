"""LLM client abstraction for the formalizer.

A tiny ``LLMClient`` protocol sits between the formalizer and Claude so tests can inject a
deterministic record/replay client — CI never calls the live API (CLAUDE.md rule 2). The
production :class:`AnthropicClient` lazy-imports the SDK, so importing this module never
requires ``anthropic``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_MODEL = "claude-opus-4-8"

# USD per 1M tokens: (input, output). Used to log cost into the draft metadata.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost in USD for a call, or 0.0 if the model's pricing is unknown."""
    rate = PRICING.get(model)
    if rate is None:
        return 0.0
    return input_tokens / 1e6 * rate[0] + output_tokens / 1e6 * rate[1]


@dataclass(frozen=True)
class Message:
    """One chat message (role is ``"user"`` or ``"assistant"``)."""

    role: str
    content: str


@dataclass(frozen=True)
class LLMResult:
    """One model completion plus its token usage."""

    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    """Anything the formalizer can call to get a completion."""

    @property
    def model(self) -> str: ...

    def complete(self, system: str, messages: list[Message], max_tokens: int) -> LLMResult: ...


class AnthropicClient:
    """Production client — calls Claude via the official SDK with adaptive thinking.

    Lazy-imports ``anthropic`` on first use; install with ``uv sync --extra formalize``.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client: object | None = None

    @property
    def model(self) -> str:
        return self._model

    def _ensure_client(self) -> object:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise ImportError(
                    "the formalizer needs the 'formalize' extra: uv sync --extra formalize"
                ) from exc
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, system: str, messages: list[Message], max_tokens: int) -> LLMResult:
        client = self._ensure_client()
        response = client.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            thinking={"type": "adaptive"},
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


@dataclass
class ReplayClient:
    """Deterministic client for tests: replays queued responses in order.

    Records every ``(system, messages)`` it was called with, so tests can assert on what the
    formalizer sent. Raises if it runs out of queued responses.
    """

    responses: list[LLMResult]
    model_name: str = "replay-model"
    calls: list[tuple[str, list[Message]]] = field(default_factory=list)
    _index: int = 0

    @property
    def model(self) -> str:
        return self.model_name

    def complete(self, system: str, messages: list[Message], max_tokens: int) -> LLMResult:
        self.calls.append((system, list(messages)))
        if self._index >= len(self.responses):
            raise AssertionError("ReplayClient ran out of queued responses")
        result = self.responses[self._index]
        self._index += 1
        return result


def replay_from_text(
    *texts: str, input_tokens: int = 1000, output_tokens: int = 500
) -> ReplayClient:
    """Build a ReplayClient from raw completion strings (fixed token counts)."""
    return ReplayClient(responses=[LLMResult(t, input_tokens, output_tokens) for t in texts])
