"""Deep research mode (Session 38, D38): gap identification, cache reuse, resume, contradiction
widening, the confidence-to-width rule, and corpus-offline determinism. CI stays offline — every
LLM round is replayed from a queued ``LLMResult``; no test touches the network."""

from __future__ import annotations

import json
from pathlib import Path

from schelling.formalizer.client import LLMResult, ReplayClient, WebSource
from schelling.formalizer.formalize import formalize
from schelling.formalizer.schemas import DraftGameSpec
from schelling.research.confidence import apply_confidence_widths, load_confidence_rule
from schelling.research.corpus import (
    corpus_to_sources,
    load_corpus,
    merge_round,
    situation_hash,
    write_corpus,
)
from schelling.research.research import run_research
from schelling.research.schemas import Claim, ResearchCorpus, ResearchSource

FIXTURES = Path(__file__).parent / "fixtures"
SITUATION = "QUESTION Q-TEST\nWhat will the group decide?"


def _result(
    claims: list[dict[str, object]], gaps: list[str], sources: list[tuple[str, str, str]]
) -> LLMResult:
    return LLMResult(
        json.dumps({"claims": claims, "gaps": gaps}),
        input_tokens=1000,
        output_tokens=500,
        searches_used=3,
        sources=tuple(WebSource(url=u, title=t, snippet=s) for u, t, s in sources),
    )


def _claim(
    text: str, conf: str, addresses: str, readings: list[float], urls: list[str]
) -> dict[str, object]:
    return {
        "text": text,
        "confidence": conf,
        "addresses": addresses,
        "readings": readings,
        "source_urls": urls,
    }


# --------------------------------------------------------------------------- the round loop (D38.1)
def test_survey_then_targeted_stops_on_no_gaps() -> None:
    r1 = _result(
        [_claim("Saudi leads", "established", "saudi.position", [66], ["http://a", "http://b"])],
        ["saudi.salience unknown"],
        [("http://a", "OPEC", "x"), ("http://b", "Reuters", "y")],
    )
    r2 = _result(
        [_claim("Saudi breakeven high", "reported", "saudi.salience", [80], ["http://c"])],
        [],  # no gaps left -> stop
        [("http://c", "IMF", "z")],
    )
    corpus = run_research(
        SITUATION, client=ReplayClient(responses=[r1, r2]), frozen_at="2026-07-24", budget=5.0
    )
    assert [rd.kind for rd in corpus.rounds] == ["survey", "targeted"]
    assert corpus.stopped_reason == "no_gaps"
    assert len(corpus.claims) == 2 and len(corpus.sources) == 3


def test_gap_identification_feeds_the_targeted_round() -> None:
    """Round 1 names a gap; round 2 (targeted) must be prompted with that exact gap (D38.1)."""
    r1 = _result(
        [_claim("A", "reported", "a.position", [50], ["http://a"])],
        ["belland.position is unknown"],
        [("http://a", "A", "")],
    )
    r2 = _result(
        [_claim("B", "reported", "belland.position", [40], ["http://x"])],
        [],
        [("http://x", "X", "")],
    )
    client = ReplayClient(responses=[r1, r2])
    run_research(SITUATION, client=client, frozen_at="2026-07-24", budget=5.0)
    round2_prompt = client.calls[1][1][0].content  # (system, messages) -> messages[0].content
    assert "belland.position is unknown" in round2_prompt
    assert "GAPS TO CLOSE" in round2_prompt


def test_stops_on_marginal_information() -> None:
    r1 = _result(
        [_claim("A", "reported", "a.position", [50], ["http://a"])],
        ["still a gap"],
        [("http://a", "A", "")],
    )
    r2 = _result([], ["still a gap"], [])  # targeted round adds nothing new -> marginal
    corpus = run_research(
        SITUATION, client=ReplayClient(responses=[r1, r2]), frozen_at="2026-07-24", budget=5.0
    )
    assert corpus.stopped_reason == "marginal"
    assert corpus.rounds[-1].new_claims == 0


def test_budget_caps_spend() -> None:
    r1 = _result(
        [_claim("A", "reported", "a.position", [50], ["http://a"])],
        ["a gap remains"],
        [("http://a", "A", "")],
    )
    corpus = run_research(
        SITUATION, client=ReplayClient(responses=[r1]), frozen_at="2026-07-24", budget=0.001
    )
    assert corpus.stopped_reason == "budget"
    assert corpus.total_cost_usd >= 0.001


def test_contradiction_round_fires_when_readings_disagree() -> None:
    r1 = _result(
        [_claim("up", "established", "x.position", [66], ["http://a", "http://b"])],
        ["more on x"],
        [("http://a", "A", ""), ("http://b", "B", "")],
    )
    r2 = _result(
        [_claim("down", "contested", "x.position", [40], ["http://c"])], [], [("http://c", "C", "")]
    )
    r3 = _result(
        [_claim("both circulate", "contested", "x.position", [40, 66], ["http://d"])],
        [],
        [("http://d", "D", "")],
    )
    corpus = run_research(
        SITUATION, client=ReplayClient(responses=[r1, r2, r3]), frozen_at="2026-07-24", budget=5.0
    )
    assert [rd.kind for rd in corpus.rounds] == ["survey", "targeted", "contradiction"]
    assert corpus.coordinate_confidence()["x.position"] == "contested"


# --------------------------------------------------------------------------- cache & resume (D38.1)
def test_cache_dedups_sources_by_url_preserving_date() -> None:
    corpus = ResearchCorpus(situation_hash="h", frozen_at="2026-07-24")
    corpus, nc, ns = merge_round(
        corpus,
        [ResearchSource(url="http://a", title="A", retrieved_at="2026-07-24")],
        [Claim(text="c1", confidence="reported", addresses="x.position")],
    )
    assert (nc, ns) == (1, 1)
    # a re-run surfaces the SAME url (different date/title) and the SAME claim -> both dropped
    corpus, nc, ns = merge_round(
        corpus,
        [ResearchSource(url="http://a", title="A2", retrieved_at="2026-08-01")],
        [Claim(text="c1", confidence="reported", addresses="x.position")],
    )
    assert (nc, ns) == (0, 0)
    assert len(corpus.sources) == 1
    assert corpus.sources[0].retrieved_at == "2026-07-24"  # original date kept


def test_resume_continues_from_a_prior_corpus(tmp_path: Path) -> None:
    r1 = _result(
        [_claim("A", "reported", "a.position", [50], ["http://a"])],
        ["gap"],
        [("http://a", "A", "")],
    )
    first = run_research(
        SITUATION, client=ReplayClient(responses=[r1]), frozen_at="2026-07-24", budget=0.001
    )  # stops on budget after 1 round
    write_corpus(tmp_path, first, SITUATION)
    prior, situation_text = load_corpus(tmp_path)
    assert prior.situation_hash == situation_hash(situation_text)
    # resume: a second round fills the gap and stops
    r2 = _result(
        [_claim("B", "reported", "b.position", [60], ["http://b"])], [], [("http://b", "B", "")]
    )
    resumed = run_research(
        situation_text,
        client=ReplayClient(responses=[r2]),
        frozen_at="2026-07-24",
        budget=5.0,
        prior=prior,
    )
    assert [rd.round for rd in resumed.rounds] == [1, 2]  # continued, not restarted
    assert len(resumed.claims) == 2 and resumed.stopped_reason == "no_gaps"


def test_corpus_roundtrips_on_disk(tmp_path: Path) -> None:
    claim = Claim(text="c", confidence="established", addresses="a.position")
    corpus = ResearchCorpus(situation_hash="h", frozen_at="2026-07-24", claims=[claim])
    write_corpus(tmp_path, corpus, SITUATION)
    loaded, text = load_corpus(tmp_path)
    assert loaded == corpus and text == SITUATION


# --------------------------------------------------------------- confidence -> width rule (D38.4)
def test_confidence_to_width_rule_from_committed_config() -> None:
    rule = load_confidence_rule()
    # established narrows, reported widens moderately, inferred widest
    assert rule.established < rule.reported < rule.inferred
    assert rule.half_width("established") == rule.established
    assert rule.half_width("reported") == rule.reported
    assert rule.half_width("inferred") == rule.inferred


def _draft_with_corpus(corpus: ResearchCorpus) -> DraftGameSpec:
    """Formalize the emission-standards replay draft with a corpus as offline evidence."""
    replay = (FIXTURES / "formalize_replay.json").read_text()
    return formalize(
        "Aland, Belland and Cesta pick a coal phase-out year.",
        sources=corpus_to_sources(corpus),
        client=ReplayClient(responses=[LLMResult(replay, 1000, 500)]),
        search=False,
        today="2026-07-24",
    )


def test_contradiction_widens_range_across_readings() -> None:
    """A contested coordinate's range spans its disagreeing readings — never one side (D38.4)."""
    corpus = ResearchCorpus(
        situation_hash="h",
        frozen_at="2026-07-24",
        claims=[
            Claim(
                text="Aland wants 2030",
                confidence="established",
                addresses="aland.position",
                readings=[10],
                source_urls=["http://a", "http://b"],
            ),
            Claim(
                text="Aland actually wants 2050",
                confidence="contested",
                addresses="aland.position",
                readings=[70],
                source_urls=["http://c"],
            ),
        ],
    )
    assert corpus.coordinate_confidence()["aland.position"] == "contested"
    draft = apply_confidence_widths(_draft_with_corpus(corpus), corpus)
    aland = next(a for a in draft.game.actors if a.id == "aland")
    # both readings (10 and 70) sit inside the widened support
    assert aland.position.low <= 10.0 and aland.position.high >= 70.0


def test_confidence_sets_width_narrow_vs_wide() -> None:
    rule = load_confidence_rule()
    corpus = ResearchCorpus(
        situation_hash="h",
        frozen_at="2026-07-24",
        claims=[
            Claim(
                text="cap sourced",
                confidence="established",
                addresses="aland.capability",
                source_urls=["http://a", "http://b"],
            ),
            # belland.position gets no claim -> inferred (widest)
        ],
    )
    draft = apply_confidence_widths(_draft_with_corpus(corpus), corpus)
    aland = next(a for a in draft.game.actors if a.id == "aland")
    belland = next(a for a in draft.game.actors if a.id == "belland")
    established_width = aland.capability.high - aland.capability.low
    inferred_width = belland.position.high - belland.position.low
    # established capability is narrow; the unsourced (inferred) position is widest (>= one half-
    # width even where a pole clamps the other side)
    assert established_width <= 2 * rule.established
    assert inferred_width >= rule.inferred - 0.01
    assert inferred_width > established_width


# --------------------------------------------------------------- corpus-offline determinism (D38.3)
def test_corpus_offline_formalize_is_deterministic() -> None:
    """Same corpus + same replayed model response => byte-identical draft (D38.3)."""
    corpus = ResearchCorpus(
        situation_hash="h",
        frozen_at="2026-07-24",
        sources=[ResearchSource(url="http://a", title="A", retrieved_at="2026-07-24", snippet="s")],
        claims=[
            Claim(
                text="Aland wants 2030",
                confidence="reported",
                addresses="aland.position",
                readings=[10],
                source_urls=["http://a"],
            )
        ],
    )
    d1 = apply_confidence_widths(_draft_with_corpus(corpus), corpus)
    d2 = apply_confidence_widths(_draft_with_corpus(corpus), corpus)
    assert d1.model_dump_json() == d2.model_dump_json()
    assert not d1.live_searched  # offline: never a live search
