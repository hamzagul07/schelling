"""Formalizer tests — schema-valid replay, the concepts-library firewall, retry loop.

CI never calls the live API: a record/replay client returns recorded completions (rule 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.formalizer.client import LLMResult, ReplayClient, cost_usd, replay_from_text
from schelling.formalizer.firewall import IndexLeakageError, find_leaks
from schelling.formalizer.formalize import FormalizeError, formalize
from schelling.formalizer.prompt import RULE_F, build_system_prompt
from schelling.formalizer.schemas import DraftExtraction
from schelling.knowledge.chunker import Chunk
from schelling.knowledge.embed import HashingEmbedder
from schelling.knowledge.index import KnowledgeIndex

FIXTURES = Path(__file__).parent / "fixtures"

SITUATION = (
    "Three regional powers -- Aland, Belland, and Cesta -- are negotiating the year to phase "
    "out coal power. Aland wants 2030, Belland wants 2040, and Cesta wants 2035. Aland is the "
    "most economically powerful of the three."
)


def _clean_draft_text() -> str:
    return (FIXTURES / "formalize_replay.json").read_text()


# ---------------------------------------------------------------- (a) schema-valid replay
def test_formalize_produces_schema_valid_draft() -> None:
    client = replay_from_text(_clean_draft_text(), input_tokens=1200, output_tokens=800)
    draft = formalize(SITUATION, client=client)
    assert draft.game.question_id == "Q-COAL-PHASEOUT"
    assert [a.id for a in draft.game.actors] == ["aland", "belland", "cesta"]
    assert draft.assumptions  # assumptions section is populated
    assert draft.template_classification.template == "multilateral_bargaining"
    # provenance logged
    assert draft.metadata.model == "replay-model"
    assert draft.metadata.input_tokens == 1200
    assert draft.metadata.cost_usd == 0.0  # unknown model -> 0 cost
    assert draft.metadata.retries == 0


def test_system_prompt_embeds_rule_f_verbatim() -> None:
    assert RULE_F in build_system_prompt()
    assert "assumptions[]" in build_system_prompt()


def test_prompt_sends_situation_and_never_auto_solves() -> None:
    client = replay_from_text(_clean_draft_text())
    formalize(SITUATION, client=client)
    system, messages = client.calls[0]
    assert "STRUCTURE" in system  # structuring role, not predicting
    assert "Aland" in messages[0].content  # situation reached the model


# ---------------------------------------------------------------- retry loop
def test_bounded_retry_recovers_from_bad_json() -> None:
    bad = LLMResult("not json at all", 100, 50)
    good = LLMResult(_clean_draft_text(), 100, 50)
    client = ReplayClient(responses=[bad, good])
    draft = formalize(SITUATION, client=client, max_retries=2)
    assert draft.metadata.retries == 1
    assert draft.metadata.input_tokens == 200  # both attempts counted
    assert len(client.calls) == 2


def test_retry_budget_exhausted_raises() -> None:
    client = ReplayClient(responses=[LLMResult("nope", 10, 10)] * 3)
    with pytest.raises(FormalizeError, match="no valid draft"):
        formalize(SITUATION, client=client, max_retries=2)


# ---------------------------------------------------------------- (b) the firewall
def _planted_index(tmp_path: Path, planted_fact: str) -> KnowledgeIndex:
    chunks = [
        Chunk(
            text=planted_fact,
            source_file="planted.txt",
            lecture="Game Theory #99: Planted",
            lecture_number=99,
            chunk_index=0,
            char_start=0,
            char_end=len(planted_fact),
        ),
        Chunk(
            text="A generic passage about coalition bargaining and the median voter.",
            source_file="planted.txt",
            lecture="Game Theory #98: Concepts",
            lecture_number=98,
            chunk_index=0,
            char_start=0,
            char_end=10,
        ),
    ]
    return KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=tmp_path / "k.db")


PLANTED_FACT = "The Zorbian Federation fields nine hundred hypersonic interceptors near its border."


def test_firewall_blocks_planted_fact_from_evidence(tmp_path: Path) -> None:
    # A draft that leaks the planted index fact into an actor's evidence note.
    leaked = json.loads(_clean_draft_text())
    leaked["game"]["actors"][0]["evidence"][0]["note"] = (
        "Zorbian Federation fields nine hundred hypersonic interceptors."
    )
    index = _planted_index(tmp_path, PLANTED_FACT)
    client = replay_from_text(json.dumps(leaked))
    with pytest.raises(IndexLeakageError) as exc:
        formalize(SITUATION, client=client, index=index)
    # The planted content, absent from the situation, is named as the leak.
    assert any("zorbian" in leak or "hypersonic" in leak for leak in exc.value.leaks)


def test_firewall_passes_clean_draft_with_index(tmp_path: Path) -> None:
    index = _planted_index(tmp_path, PLANTED_FACT)
    client = replay_from_text(_clean_draft_text())
    draft = formalize(SITUATION, client=client, index=index)
    # The planted fact appears nowhere in any evidence note.
    all_notes = " ".join(ev.note for a in draft.game.actors for ev in a.evidence).lower()
    assert "zorbian" not in all_notes
    assert "hypersonic" not in all_notes


def test_find_leaks_detects_shingle_overlap() -> None:
    draft = DraftExtraction.model_validate(json.loads(_clean_draft_text()))
    # Nothing leaks when the concepts text shares no unique phrase with the factual surface.
    assert find_leaks(draft, allowed_text=SITUATION, concepts_text="median voter theorem") == []


def test_cost_usd_uses_opus_pricing() -> None:
    # 1M input + 1M output at Opus 4.8 rates = 5 + 25.
    assert cost_usd("claude-opus-4-8", 1_000_000, 1_000_000) == pytest.approx(30.0)
    assert cost_usd("unknown-model", 1_000_000, 0) == 0.0
