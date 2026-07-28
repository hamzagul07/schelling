"""Pluggable search backends behind one interface (Session 46, D46.1).

The formalizer can research a situation through more than one search provider. The default is
Anthropic's server-side ``web_search`` (Claude runs the search inside its own call); the alternative
is **Exa**, which we call directly and feed the results in as evidence. Both are selected by config,
take their key from the environment, and fall back gracefully when a key is absent. Every fetched
source records **which backend served it** (``FetchedSource.backend``), so a draft states how it was
researched.

The Anthropic backend is a label, not a client here — its search happens inside the LLM call, so
:func:`select_backend` returns ``None`` for it and the formalizer takes its existing ``--search``
path. The Exa backend is a real client over the shared :class:`FetchSession` (cached, budgeted,
replay-testable), so CI never calls it live.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from schelling.evidence.http import FetchSession

ANTHROPIC = "anthropic"
EXA = "exa"
KNOWN_BACKENDS = (ANTHROPIC, EXA)

_EXA_URL = "https://api.exa.ai/search"
EXA_COST_PER_SEARCH = 0.005  # USD (Exa list price ~ $5 / 1000 searches)


@dataclass(frozen=True)
class SearchResult:
    """One search hit: the source, a snippet, and the backend that served it."""

    url: str
    title: str
    snippet: str
    backend: str


class SearchBackend(Protocol):
    """A search provider we call directly to gather candidate evidence sources."""

    @property
    def name(self) -> str: ...

    def search(self, query: str, *, k: int = 5) -> list[SearchResult]: ...


class ExaBackend:
    """Exa search over the shared fetch session (POST /search with a JSON body, ``x-api-key``)."""

    name = EXA

    def __init__(self, api_key: str, session: FetchSession) -> None:
        self._key = api_key
        self._session = session

    def search(self, query: str, *, k: int = 5) -> list[SearchResult]:
        body = {"query": query, "numResults": k, "contents": {"text": {"maxCharacters": 500}}}
        data = self._session.fetch_json(
            _EXA_URL, method="POST", body=body, headers={"x-api-key": self._key}
        )
        results: list[SearchResult] = []
        for item in data.get("results", []):
            url = item.get("url")
            if not url:
                continue
            text = item.get("text") or item.get("snippet") or ""
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title") or "",
                    snippet=" ".join(str(text).split())[:300],
                    backend=EXA,
                )
            )
        return results


def select_backend(
    name: str,
    *,
    session: FetchSession | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, SearchBackend | None]:
    """Resolve a backend name to ``(effective_name, backend_or_None)`` with fallback (D46.1).

    ``anthropic`` (the default) returns ``(anthropic, None)`` — the formalizer runs server-side
    search itself. ``exa`` returns an :class:`ExaBackend` when ``EXA_API_KEY`` is set and a session
    is given; if the key is missing it falls back to ``anthropic``, not failing. An unknown name
    also falls back to ``anthropic``.
    """
    environ = env if env is not None else dict(os.environ)
    if name == EXA:
        key = environ.get("EXA_API_KEY", "").strip()
        if key and session is not None:
            return EXA, ExaBackend(key, session)
        return ANTHROPIC, None  # graceful fallback: no key -> the default backend
    return ANTHROPIC, None
