"""Evidence-acquisition layer (Session 46, D46): fetch/cache/budget, search backends, GDELT
precedents, Metaculus crowd, and literature. Replay fixtures only — CI never calls a live API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.evidence.gdelt import (
    GDELT_DOC_URL,
    candidates_to_precedent_set,
    gdelt_candidates,
)
from schelling.evidence.http import (
    Budget,
    BudgetError,
    FetchSession,
    ReplayFetcher,
)
from schelling.evidence.literature import literature_lookup
from schelling.evidence.metaculus import (
    MetaculusMatch,
    build_crowd_record,
    metaculus_question,
    metaculus_search,
)
from schelling.evidence.search import ExaBackend, SearchResult, select_backend
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor, TriangularEstimate


def _session(
    responses: dict[str, str], *, budget: int = 10, cache: Path | None = None
) -> FetchSession:
    return FetchSession(
        ReplayFetcher(responses=responses),
        today="2026-07-28",
        cache_dir=cache,
        budget=Budget(budget),
    )


def _game() -> GameSpec:
    return GameSpec(
        question_id="Q-DEMO",
        frozen_at="2026-07-28",
        continuum=Continuum(label="l", anchor_0="0", anchor_100="100"),
        actors=[
            Actor(
                id="a",
                name="A",
                position=TriangularEstimate.point(50.0),
                salience=TriangularEstimate.point(50.0),
                capability=TriangularEstimate.point(50.0),
                evidence=[],
            )
        ],
        template="t",
        horizon="h",
        resolution_rubric=ResolutionRubric(
            resolution_criteria="c",
            adjudicating_sources=["s"],
            outcome_mapping="m",
            grading_formula="score = |median - actual|",
            bands=[
                RubricBand(lo=0.0, hi=50.0, label="no"),
                RubricBand(lo=51.0, hi=100.0, label="yes"),
            ],
            binary_met_bands=["yes"],  # a crowd baseline needs this declared (D47.1)
        ),
    )


# --------------------------------------------------------------- fetch / cache / budget (D46.5)
def test_fetch_caches_by_url_and_does_not_recharge(tmp_path: Path) -> None:
    sess = _session({"https://x.test/a": '{"ok": 1}'}, budget=1, cache=tmp_path)
    first = sess.fetch_json("https://x.test/a")
    second = sess.fetch_json("https://x.test/a")  # same URL -> cache hit, no second charge
    assert first == second == {"ok": 1}
    assert sess.budget is not None and sess.budget.spent == 1  # only the first fetch charged
    assert sum(1 for f in sess.fetches if f.from_cache) == 1
    assert "served from cache" in sess.spend_report()


def test_budget_cap_raises_when_exhausted() -> None:
    sess = _session({"https://x.test/a": "1", "https://x.test/b": "2"}, budget=1)
    sess.fetch_text("https://x.test/a")
    with pytest.raises(BudgetError, match="budget"):
        sess.fetch_text("https://x.test/b")


def test_retrieval_date_is_recorded_from_today() -> None:
    sess = _session({"https://x.test/a": "1"})
    sess.fetch_text("https://x.test/a")
    assert sess.fetches[0].retrieved_at == "2026-07-28"


# --------------------------------------------------------------- search backends (D46.1)
def test_select_backend_defaults_to_anthropic() -> None:
    name, backend = select_backend("anthropic", env={})
    assert name == "anthropic" and backend is None


def test_exa_falls_back_to_anthropic_without_a_key() -> None:
    sess = _session({})
    name, backend = select_backend("exa", session=sess, env={})  # no EXA_API_KEY
    assert name == "anthropic" and backend is None


def test_exa_backend_searches_and_tags_sources() -> None:
    body = json.dumps(
        {"results": [{"url": "https://s.test/1", "title": "One", "text": "a fact about it"}]}
    )
    sess = _session({"https://api.exa.ai/search": body})
    name, backend = select_backend("exa", session=sess, env={"EXA_API_KEY": "k"})
    assert name == "exa" and isinstance(backend, ExaBackend)
    results = backend.search("query", k=3)
    assert results == [
        SearchResult(url="https://s.test/1", title="One", snippet="a fact about it", backend="exa")
    ]


# --------------------------------------------------------------- GDELT -> precedents (D46.2)
def test_gdelt_candidates_become_unratified_proposals() -> None:
    body = json.dumps(
        {
            "articles": [
                {
                    "url": "https://n.test/x",
                    "title": "US-Iran talks",
                    "seendate": "20240115T120000Z",
                    "domain": "n.test",
                },
                {
                    "url": "https://n.test/x",
                    "title": "dup",
                    "seendate": "20240115T120000Z",
                },  # duplicate URL
                {
                    "url": "https://n.test/y",
                    "title": "another",
                    "seendate": "20240220T000000Z",
                    "domain": "m.test",
                },
            ]
        }
    )
    sess = _session({GDELT_DOC_URL: body})
    cands = gdelt_candidates(
        sess, "US Iran", start_date="2024-01-01", end_date="2024-12-31", cameo="057"
    )
    assert [c.url for c in cands] == ["https://n.test/x", "https://n.test/y"]  # deduped by URL
    assert cands[0].date == "2024-01-15" and cands[0].cameo == "057"
    pset = candidates_to_precedent_set(cands, "Q-DEMO")
    assert pset.source_model == "gdelt"
    assert pset.ratification_note == ""  # UNRATIFIED — the panel will not use it
    assert all(not p.ratified for p in pset.precedents)
    assert "PENDING" in pset.precedents[0].reasoning


# --------------------------------------------------------------- Metaculus crowd (D46.3)
def test_metaculus_search_and_crowd_record() -> None:
    search_body = json.dumps(
        {
            "results": [
                {
                    "id": 42,
                    "title": "Will X happen?",
                    "community_prediction": 0.6,
                    "number_of_forecasters": 120,
                }
            ]
        }
    )
    q_body = json.dumps(
        {
            "id": 42,
            "title": "Will X happen?",
            "community_prediction": 0.6,
            "number_of_forecasters": 120,
        }
    )
    sess = _session({"https://www.metaculus.com/api2/questions/": search_body})
    matches = metaculus_search(sess, "topic")
    assert matches[0].metaculus_id == 42 and matches[0].community_prediction == pytest.approx(0.6)

    sess2 = _session({"https://www.metaculus.com/api2/questions/42/": q_body})
    match = metaculus_question(sess2, 42)
    rec = build_crowd_record(_game(), match, placement=60.0, justification="same event and window")
    assert rec.model == "crowd-metaculus"
    assert rec.ensemble.median == 60.0
    # seal-shaped: model + ensemble.median + game.frozen_at + resolution_rubric present
    dump = rec.model_dump()
    assert dump["game"]["frozen_at"] == "2026-07-28"
    assert dump["game"]["resolution_rubric"] is not None
    assert rec.metaculus_id == 42


def test_crowd_record_requires_written_justification() -> None:
    sess = _session({"https://www.metaculus.com/api2/questions/7/": json.dumps({"id": 7})})
    match = metaculus_question(sess, 7)
    with pytest.raises(ValueError, match="justified in writing"):
        build_crowd_record(_game(), match, placement=50.0, justification="   ")


def test_crowd_record_seals_as_crowd_metaculus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from schelling import cli

    monkeypatch.setattr("schelling.cli.stamp_ledger", lambda _l, _p: (None, "anchoring skipped"))
    match = MetaculusMatch(
        metaculus_id=42,
        title="Will X?",
        url="https://m/q/42/",
        community_prediction=0.6,
        n_forecasters=100,
        close_time="",
    )
    rec = build_crowd_record(_game(), match, placement=60.0, justification="genuine match")
    rec_file = tmp_path / "crowd.json"
    rec_file.write_text(rec.model_dump_json(indent=2) + "\n")
    ledger = tmp_path / "L.md"
    result = CliRunner().invoke(
        cli.app, ["seal", str(rec_file), "--vintage", "crowd", "-o", str(ledger)]
    )
    assert result.exit_code == 0, result.output
    row = ledger.read_text()
    assert "crowd-metaculus" in row and "60.000" in row  # the ledger row records the crowd baseline


# --------------------------------------------------------------- CLI wiring (replay, no live API)
def test_gdelt_cli_writes_unratified_precedents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from schelling import cli
    from schelling.precedents.schemas import PrecedentSet

    fixture = tmp_path / "q.json"
    fixture.write_text(_game().model_dump_json())
    body = json.dumps(
        {
            "articles": [
                {
                    "url": "https://n.test/x",
                    "title": "t",
                    "seendate": "20240115T120000Z",
                    "domain": "n.test",
                }
            ]
        }
    )
    monkeypatch.setattr(
        cli, "_live_session", lambda b, c=0.0: _session({GDELT_DOC_URL: body}, budget=b)
    )
    out = tmp_path / "out.precedents.json"
    result = CliRunner().invoke(
        cli.app,
        [
            "gdelt",
            str(fixture),
            "--query",
            "US Iran",
            "--from",
            "2024-01-01",
            "--to",
            "2024-12-31",
            "--cameo",
            "057",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    pset = PrecedentSet.model_validate_json(out.read_text())
    assert pset.source_model == "gdelt" and pset.ratification_note == ""
    assert pset.precedents and not pset.precedents[0].ratified


# --------------------------------------------------------------- literature (D46.4)
def test_literature_lookup_finds_open_versions() -> None:
    work = json.dumps(
        {
            "title": "A paper",
            "doi": "https://doi.org/10.1/abc",
            "best_oa_location": {
                "pdf_url": "https://oa.test/paper.pdf",
                "version": "publishedVersion",
            },
        }
    )
    sess = _session({"https://api.openalex.org/works/https://doi.org/10.1/abc": work})
    result = literature_lookup(sess, "10.1/abc")
    assert result.is_open and result.title == "A paper"
    assert result.versions[0].url == "https://oa.test/paper.pdf"
    assert result.versions[0].source == "openalex"
