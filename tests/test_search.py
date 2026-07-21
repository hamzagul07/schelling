"""Live-search formalizer tests (Session 8).

CI stays offline: the client's block-parsing is exercised against a recorded API response
(``web_search_response.json``), and the formalize-level tests inject a ReplayClient carrying
fetched sources. No test touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from schelling.formalizer.client import (
    AnthropicClient,
    LLMResult,
    ReplayClient,
    WebSearchUnavailableError,
    WebSource,
    search_cost_usd,
)
from schelling.formalizer.firewall import IndexLeakageError
from schelling.formalizer.formalize import formalize
from schelling.formalizer.prompt import build_system_prompt
from schelling.knowledge.chunker import Chunk
from schelling.knowledge.embed import HashingEmbedder
from schelling.knowledge.index import KnowledgeIndex

FIXTURES = Path(__file__).parent / "fixtures"

SITUATION = (
    "Three regional powers -- Aland, Belland, and Cesta -- are negotiating the year to phase "
    "out coal power. Aland wants 2030, Belland wants 2040, and Cesta wants 2035."
)
PLANTED_FACT = "The Zorbian Federation fields nine hundred hypersonic interceptors near its border."


def _clean_draft_text() -> str:
    return (FIXTURES / "formalize_replay.json").read_text()


def _planted_index(tmp_path: Path, fact: str) -> KnowledgeIndex:
    chunks = [
        Chunk(fact, "planted.txt", "Game Theory #99: Planted", 99, 0, 0, len(fact)),
        Chunk(
            "A generic passage about coalition bargaining and the median voter.",
            "planted.txt",
            "Game Theory #98: Concepts",
            98,
            0,
            0,
            10,
        ),
    ]
    return KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=tmp_path / "k.db")


# --------------------------------------------------------------- client block parsing (offline)
def _ns(obj: Any) -> Any:
    """Recursively turn the recorded JSON response into attribute-access objects (like the SDK)."""
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_ns(v) for v in obj]
    return obj


class _FakeMessages:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self._response


def test_client_parses_web_search_blocks() -> None:
    response = _ns(json.loads((FIXTURES / "web_search_response.json").read_text()))
    client = AnthropicClient(model="claude-opus-4-8")
    fake = _FakeMessages(response)
    client._client = SimpleNamespace(messages=fake)  # inject; no network

    result = client.complete("sys", [], 1000, search=True, max_searches=5)

    # The web-search tool was enabled with the current type and the max-uses budget.
    tool = fake.kwargs["tools"][0]
    assert tool["type"] == "web_search_20260209" and tool["max_uses"] == 5
    # Text is assembled from text blocks only; tool blocks are excluded.
    assert result.text.startswith("{") and "draft json" in result.text
    # Both fetched results become sources; the cited passage is the snippet.
    assert result.searches_used == 2
    assert [s.url for s in result.sources] == [
        "https://example.org/aland-coal-policy",
        "https://example.net/belland-energy-review",
    ]
    assert "2030 phase-out" in result.sources[0].snippet  # from the citation's cited_text
    assert result.input_tokens == 4200 and result.output_tokens == 900


def test_client_maps_tool_rejection_to_friendly_error() -> None:
    class _Boom:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("tools.0: web_search is not supported for this account")

    client = AnthropicClient()
    client._client = SimpleNamespace(messages=_Boom())
    with pytest.raises(WebSearchUnavailableError, match="re-run without --search"):
        client.complete("sys", [], 100, search=True)


def test_search_prompt_marks_fetched_sources_as_evidence() -> None:
    assert "EVIDENCE" in build_system_prompt(search=True)
    assert "web_search" in build_system_prompt(search=True)
    assert "web_search" not in build_system_prompt(search=False)  # off by default


# --------------------------------------------------------------- firewall: fetched fact IS evidence
def _leaked_note_draft() -> str:
    d = json.loads(_clean_draft_text())
    d["game"]["actors"][0]["evidence"][0]["note"] = (
        "Zorbian Federation fields nine hundred hypersonic interceptors."
    )
    return json.dumps(d)


def _searched_client(text: str, snippet: str, *, searches: int = 2) -> ReplayClient:
    source = WebSource(url="https://src.example/zorbia", title="Zorbia brief", snippet=snippet)
    return ReplayClient([LLMResult(text, 100, 50, searches_used=searches, sources=(source,))])


def test_fetched_snippet_fact_is_allowed_as_evidence(tmp_path: Path) -> None:
    # The same distinctive fact lives in BOTH the concept index and a fetched source. Without
    # search it would be a leak; because it arrives as fetched EVIDENCE it is allowed.
    index = _planted_index(tmp_path, PLANTED_FACT)
    client = _searched_client(_leaked_note_draft(), snippet=PLANTED_FACT)
    draft = formalize(
        SITUATION, client=client, index=index, search=True, today="2026-07-21", max_leak_retries=0
    )
    note = draft.game.actors[0].evidence[0].note.lower()
    assert "zorbian" in note  # the fetched fact survived into the evidence note, not blocked
    assert draft.live_searched is True
    assert draft.metadata.searches_used == 2


def test_concept_library_still_blocked_under_search(tmp_path: Path) -> None:
    # Search on, but the leaked fact is concept-only (in no fetched snippet) -> still blocked.
    index = _planted_index(tmp_path, PLANTED_FACT)
    client = _searched_client(_leaked_note_draft(), snippet="unrelated coastal weather summary")
    with pytest.raises(IndexLeakageError) as exc:
        formalize(
            SITUATION,
            client=client,
            index=index,
            search=True,
            today="2026-07-21",
            max_leak_retries=0,
        )
    assert any("zorbian" in leak.phrase or "hypersonic" in leak.phrase for leak in exc.value.leaks)


# --------------------------------------------------------------- freeze discipline + provenance
def test_search_forces_frozen_at_to_today_and_records_sources(tmp_path: Path) -> None:
    client = _searched_client(_clean_draft_text(), snippet="Aland targets a 2030 coal exit.")
    draft = formalize(SITUATION, client=client, search=True, today="2026-07-21")
    assert draft.live_searched is True
    assert draft.game.frozen_at == "2026-07-21"  # cannot be frozen in the past
    assert len(draft.sources_fetched) == 1
    s = draft.sources_fetched[0]
    assert s.url == "https://src.example/zorbia" and s.retrieved_at == "2026-07-21"
    # cost line includes the search cost ($10 / 1000 searches).
    assert draft.metadata.cost_usd == pytest.approx(search_cost_usd(2), abs=1e-9)


def test_no_search_leaves_draft_unfrozen_and_sourceless() -> None:
    client = ReplayClient([LLMResult(_clean_draft_text(), 100, 50)])
    draft = formalize(SITUATION, client=client, search=False)
    assert draft.live_searched is False
    assert draft.sources_fetched == []
    assert draft.game.frozen_at == "2026-07-21"  # the model's value, untouched
    assert draft.metadata.searches_used == 0


def test_search_formalize_is_deterministic(tmp_path: Path) -> None:
    def run() -> str:
        client = _searched_client(_clean_draft_text(), snippet="Aland targets a 2030 coal exit.")
        return formalize(
            SITUATION, client=client, search=True, today="2026-07-21"
        ).model_dump_json()

    assert run() == run()
