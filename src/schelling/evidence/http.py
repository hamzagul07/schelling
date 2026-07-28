"""HTTP fetch layer for the evidence-acquisition commands (Session 46, D46.5).

Every external fetch in the evidence layer goes through a :class:`FetchSession`, which gives three
things the milestone requires: **caching by URL with a retrieval date** (a repeated URL is served
from disk and never re-charged), a **per-command budget cap** with a **spend report**, and an
**injectable fetcher** so CI never touches the network — tests pass a :class:`ReplayFetcher` with
canned bodies (CLAUDE.md rule 2). The live :class:`UrllibFetcher` uses only the standard library, so
the evidence layer adds no dependency.

Determinism: the retrieval date is supplied (``today``), not read from a wall clock, so a replayed
session is byte-reproducible.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class FetchError(RuntimeError):
    """A live fetch failed (network, HTTP error, or timeout)."""


class BudgetError(RuntimeError):
    """The per-command fetch budget was exhausted before the command finished."""


class Fetcher(Protocol):
    """Anything that can turn a request into a response body (real HTTP, or a replay for tests)."""

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class Fetched:
    """One fetched resource: its body, when it was retrieved, and whether it came from cache."""

    url: str
    retrieved_at: str  # ISO date the resource was first fetched
    body: str
    from_cache: bool = False


class UrllibFetcher:
    """Live fetcher over stdlib ``urllib.request`` — GET, or POST with a JSON body."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        hdrs = {"User-Agent": "schelling-evidence/1.0", **(headers or {})}
        if data is not None:
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return str(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FetchError(f"fetch failed for {url}: {exc}") from exc


@dataclass
class ReplayFetcher:
    """Deterministic fetcher for tests: canned body per request key; records every call."""

    responses: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        key = _request_key(url, method, body)
        self.calls.append(key)
        if key in self.responses:
            return self.responses[key]
        if url in self.responses:  # keying by the bare URL
            return self.responses[url]
        for registered, canned in self.responses.items():  # keying by a URL prefix (query-agnostic)
            if url.startswith(registered):
                return canned
        raise FetchError(f"ReplayFetcher has no canned response for {key}")


@dataclass
class Budget:
    """A per-command cap on live fetches and the running spend it implies (D46.5)."""

    max_fetches: int
    cost_per_fetch: float = 0.0  # USD; 0 for free APIs (GDELT, Metaculus, OpenAlex)
    spent: int = 0

    def charge(self) -> None:
        if self.spent + 1 > self.max_fetches:
            raise BudgetError(
                f"fetch budget of {self.max_fetches} exhausted; raise --budget to fetch more"
            )
        self.spent += 1

    @property
    def spend_usd(self) -> float:
        return round(self.spent * self.cost_per_fetch, 6)


def _request_key(url: str, method: str, body: dict[str, Any] | None) -> str:
    payload = f"{method} {url}"
    if body is not None:
        payload += " " + json.dumps(body, sort_keys=True, separators=(",", ":"))
    return payload


def _cache_name(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24] + ".json"


@dataclass
class FetchSession:
    """A cached, budgeted, injectable fetch session shared across an evidence command (D46.5).

    Caches each distinct request under ``cache_dir`` keyed by (method, url, body), recording the
    retrieval date; a cache hit is free (never charged to the budget). ``fetches`` accumulates the
    provenance of every request (url, retrieval date, cache flag) for the command's report.
    """

    fetcher: Fetcher
    today: str
    cache_dir: Path | None = None
    budget: Budget | None = None
    fetches: list[Fetched] = field(default_factory=list)

    def fetch_text(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        key = _request_key(url, method, body)
        cached = self._cache_get(key)
        if cached is not None:
            self.fetches.append(
                Fetched(url, cached["retrieved_at"], cached["body"], from_cache=True)
            )
            return str(cached["body"])
        if self.budget is not None:
            self.budget.charge()
        text = self.fetcher.fetch(url, method=method, body=body, headers=headers)
        self._cache_put(key, {"url": url, "retrieved_at": self.today, "body": text})
        self.fetches.append(Fetched(url, self.today, text, from_cache=False))
        return text

    def fetch_json(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return json.loads(self.fetch_text(url, method=method, body=body, headers=headers))

    def spend_report(self) -> str:
        live = sum(1 for f in self.fetches if not f.from_cache)
        cached = sum(1 for f in self.fetches if f.from_cache)
        spend = self.budget.spend_usd if self.budget is not None else 0.0
        return f"{live} live fetch(es), {cached} served from cache; spend ${spend:.4f}"

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / _cache_name(key)
        if not path.exists():
            return None
        return json.loads(path.read_text())  # type: ignore[no-any-return]

    def _cache_put(self, key: str, value: dict[str, Any]) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / _cache_name(key)).write_text(json.dumps(value, indent=2) + "\n")
