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

# The current server-side web-search tool type (Anthropic API, Opus 4.8 era). See CLAUDE-API drift.
WEB_SEARCH_TOOL_TYPE = "web_search_20260209"

# USD per 1M tokens: (input, output). Used to log cost into the draft metadata.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

# Server-side web search is billed per 1,000 searches (Anthropic list price).
WEB_SEARCH_USD_PER_1K = 10.0


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Token cost in USD for a call, or 0.0 if the model's pricing is unknown."""
    rate = PRICING.get(model)
    if rate is None:
        return 0.0
    return input_tokens / 1e6 * rate[0] + output_tokens / 1e6 * rate[1]


def search_cost_usd(searches: int) -> float:
    """USD cost of ``searches`` server-side web searches."""
    return searches / 1000.0 * WEB_SEARCH_USD_PER_1K


class WebSearchUnavailableError(RuntimeError):
    """The account/API rejected the server-side web-search tool."""


@dataclass(frozen=True)
class Message:
    """One chat message (role is ``"user"`` or ``"assistant"``)."""

    role: str
    content: str


@dataclass(frozen=True)
class WebSource:
    """One source Claude fetched via server-side web search (evidence-river material)."""

    url: str
    title: str
    snippet: str = ""


@dataclass(frozen=True)
class LLMResult:
    """One model completion: text, token usage, and (when search ran) the fetched sources."""

    text: str
    input_tokens: int
    output_tokens: int
    searches_used: int = 0
    sources: tuple[WebSource, ...] = ()


class LLMClient(Protocol):
    """Anything the formalizer can call to get a completion."""

    @property
    def model(self) -> str: ...

    def complete(
        self,
        system: str,
        messages: list[Message],
        max_tokens: int,
        *,
        search: bool = False,
        max_searches: int = 5,
        temperature: float | None = None,
    ) -> LLMResult: ...


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

    def complete(
        self,
        system: str,
        messages: list[Message],
        max_tokens: int,
        *,
        search: bool = False,
        max_searches: int = 5,
        temperature: float | None = None,
    ) -> LLMResult:
        client = self._ensure_client()
        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        # An explicit temperature elicits an independently-sampled judgment (used by
        # llm-forecast, D27.1); otherwise use adaptive thinking. The two are mutually exclusive.
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["thinking"] = {"type": "adaptive"}
        if search:
            kwargs["tools"] = [
                {"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": max_searches}
            ]
        try:
            response = client.messages.create(**kwargs)  # type: ignore[attr-defined]
        except Exception as exc:  # map a tool rejection to a friendly error, re-raise otherwise
            if search and _looks_like_tool_rejection(exc):
                raise WebSearchUnavailableError(
                    "web search was rejected by the API for this account; re-run without --search."
                ) from exc
            raise
        return _parse_response(response)


def _looks_like_tool_rejection(exc: Exception) -> bool:
    """Heuristic: an API 4xx that names the web-search tool (account not enabled / bad type)."""
    msg = str(exc).lower()
    return "web_search" in msg or ("tool" in msg and ("not " in msg or "unsupported" in msg))


def _parse_response(response: object) -> LLMResult:
    """Assemble text + fetched sources + search count from a (possibly multi-block) response.

    Blocks: ``text`` (with optional ``citations``), ``server_tool_use`` (the query, ignored), and
    ``web_search_tool_result`` (a list of ``web_search_result`` items). Snippets are taken from the
    text blocks' citations (the passages Claude actually quoted) when available.
    """
    content = getattr(response, "content", []) or []
    # url -> the passage Claude cited from it, used as the source snippet.
    snippets: dict[str, str] = {}
    for block in content:
        if getattr(block, "type", None) == "text":
            for cite in getattr(block, "citations", None) or []:
                url = getattr(cite, "url", None)
                cited = getattr(cite, "cited_text", None)
                if url and cited and url not in snippets:
                    snippets[url] = " ".join(str(cited).split())[:300]

    text = "".join(
        b.text for b in content if getattr(b, "type", None) == "text" and getattr(b, "text", None)
    )
    sources: list[WebSource] = []
    seen: set[str] = set()
    for block in content:
        if getattr(block, "type", None) != "web_search_tool_result":
            continue
        for item in getattr(block, "content", None) or []:
            if getattr(item, "type", None) != "web_search_result":
                continue
            url = getattr(item, "url", None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                WebSource(
                    url=url,
                    title=getattr(item, "title", "") or "",
                    snippet=snippets.get(url, ""),
                )
            )

    usage = response.usage  # type: ignore[attr-defined]
    stu = getattr(usage, "server_tool_use", None)
    searches_used = int(getattr(stu, "web_search_requests", 0) or 0) if stu is not None else 0
    return LLMResult(
        text=text,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        searches_used=searches_used,
        sources=tuple(sources),
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

    def complete(
        self,
        system: str,
        messages: list[Message],
        max_tokens: int,
        *,
        search: bool = False,
        max_searches: int = 5,
        temperature: float | None = None,
    ) -> LLMResult:
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
