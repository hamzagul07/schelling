"""Report renderer tests: golden output, determinism, offline-cleanliness, type detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from schelling.report.render import render, render_forecast
from schelling.schemas.forecast import ForecastRecord

FIXTURES = Path(__file__).parent / "fixtures" / "report"

# Tokens that would indicate a network fetch (the report must reference none of them).
_NETWORK_TOKENS = ("http://", "https://", "src=", "<link", "@import", "url(", "<script")


def _load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((FIXTURES / name).read_text()))


# --------------------------------------------------------------- (a) golden render tests
def test_forecast_report_matches_golden() -> None:
    html = render(_load("forecast_record.json"))
    assert html == (FIXTURES / "forecast_report.html").read_text()


def test_draft_report_matches_golden() -> None:
    html = render(_load("draft.json"))
    assert html == (FIXTURES / "draft_report.html").read_text()


def test_advise_report_matches_golden() -> None:
    html = render(_load("advise.json"))
    assert html == (FIXTURES / "advise_report.html").read_text()


def test_searched_draft_report_matches_golden() -> None:
    html = render(_load("draft_searched.json"))
    assert html == (FIXTURES / "draft_searched_report.html").read_text()


def test_backtest_report_matches_golden() -> None:
    html = render(_load("backtest.json"))
    assert html == (FIXTURES / "backtest_report.html").read_text()


def test_render_is_deterministic() -> None:
    data = _load("forecast_record.json")
    assert render(data) == render(data)


# --------------------------------------------------------------- offline / self-contained
@pytest.mark.parametrize(
    "name", ["forecast_record.json", "draft.json", "advise.json", "backtest.json"]
)
def test_report_references_no_external_resources(name: str) -> None:
    html = render(_load(name)).lower()
    for token in _NETWORK_TOKENS:
        assert token not in html, f"{name} contains network token {token!r}"
    assert html.startswith("<!doctype html>")
    assert "<style>" in html  # CSS is inlined, not linked


# --------------------------------------------------------------- content sanity
def test_forecast_report_has_all_sections() -> None:
    html = render(_load("forecast_record.json"))
    for heading in (
        "Headline",
        "Actor map",
        "Outcome distribution",
        "Sensitivity",
        "Median trajectory",
        "Inputs",
    ):
        assert heading in html
    assert "settlement median" in html
    assert "settle-line" in html  # settlement marker on the actor map
    assert "inputs_hash" in html and "engine" in html  # provenance footer


def test_draft_report_has_review_sections() -> None:
    html = render(_load("draft.json"))
    assert "Draft game specification" in html
    assert "Stakeholders" in html
    assert "Open assumptions" in html
    assert 'class="checklist"' in html  # assumptions rendered as a checklist
    assert "Provenance" in html


# --------------------------------------------------------------- type detection / robustness
def test_render_rejects_unknown_artifact() -> None:
    with pytest.raises(ValueError, match="unrecognized artifact"):
        render({"not": "an artifact"})


def test_render_rejects_bare_gamespec() -> None:
    game = _load("draft.json")["game"]  # a GameSpec dict, no assumptions/ensemble
    with pytest.raises(ValueError, match="unrecognized artifact"):
        render(game)


def test_forecast_report_without_game_is_graceful() -> None:
    record = ForecastRecord.model_validate(_load("forecast_record.json"))
    legacy = record.model_copy(update={"game": None, "median_trajectory": []})
    html = render_forecast(legacy)
    # No actor map or inputs section (they need the game), but the rest still renders.
    assert "Outcome distribution" in html
    assert "Actor map" not in html
    assert "Inputs" not in html


# --------------------------------------------------------------- draft provenance end-to-end (D6.8)
def test_forecast_report_renders_carried_assumptions_and_provenance() -> None:
    from schelling.formalizer.schemas import DraftGameSpec
    from schelling.mc.monte_carlo import forecast
    from schelling.solver.config import SolverConfig

    draft = DraftGameSpec.model_validate(_load("draft.json"))
    record = forecast(
        draft.game,
        SolverConfig(),
        n_draws=40,
        seed=1,
        write=False,
        assumptions=draft.assumptions,
        formalizer_metadata=draft.metadata,
    )
    html = render(json.loads(record.model_dump_json()))
    assert "Assumptions carried from the draft" in html
    assert draft.assumptions[0].statement in html  # the assumption text is rendered
    assert "formalizer</dt>" in html and draft.metadata.model in html  # provenance chain


# --------------------------------------------------------------- named-reason detection (D6.9)
def test_render_old_schema_record_names_the_reason() -> None:
    old = {"run_id": "x", "question_id": "Q", "forecast_median": 9.5}  # pre-ensemble schema
    with pytest.raises(ValueError, match="older schema"):
        render(old)


def test_render_malformed_forecast_names_the_reason() -> None:
    bad = {"run_id": "x", "question_id": "Q", "ensemble": {"median": "not-a-number"}}
    with pytest.raises(ValueError, match="does not match the current schema"):
        render(bad)


# --------------------------------------------------------------- advise report (D7.x)
# --------------------------------------------------------------- sources_fetched (D8.4)
def test_searched_draft_report_renders_linked_source_list() -> None:
    html = render(_load("draft_searched.json"))
    assert "Sources fetched" in html and "live-searched" in html
    assert 'class="sources"' in html
    # each fetched source is a clickable link with its retrieval date
    assert '<a href="https://example.org/aland-coal-policy"' in html
    assert "retrieved 2026-07-21" in html


def test_searched_draft_report_loads_no_external_resource() -> None:
    # A hyperlink to a cited source is fine (nothing loads on open); resource-loading tokens
    # must still be absent, so the report stays self-contained and offline (D8.4).
    html = render(_load("draft_searched.json")).lower()
    for token in ("<script", "<link", "src=", "@import", "url("):
        assert token not in html, f"draft_searched contains resource token {token!r}"
    assert 'href="https://' in html  # but hyperlinks to sources are present and expected


# --------------------------------------------------------------- backtest report (D9.x)
def test_backtest_report_has_gate_verdict_and_context() -> None:
    html = render(_load("backtest.json"))
    for heading in (
        "Mean absolute error by method",
        "Error distribution",
        "Worst issues",
        "Published DEU error rates",
    ):
        assert heading in html
    assert "Gate FAILED" in html or "Gate PASSED" in html  # a verdict is stated
    assert 'class="verdict' in html
    assert "Bueno de Mesquita" in html  # cited context
    assert "dataset_sha256" in html  # provenance


def test_backtest_report_shows_fair_fight_sections() -> None:
    html = render(_load("backtest.json"))
    assert "sourced treaty-regime capabilities" in html  # capability mode surfaced
    assert "Split-sample validation" in html  # item-4 validation section
    assert "challenge_rp" in html or "rp-anchored" in html  # the rp variant is a method


def test_forecast_report_shows_model() -> None:
    html = render(_load("forecast_record.json"))
    assert "challenge model" in html  # the model is named in the header


def test_backtest_report_rejects_bad_schema() -> None:
    bad = {"methods": [], "gate_passed": True, "primary_method": "x"}  # backtest-shaped but invalid
    with pytest.raises(ValueError, match="BacktestRecord"):
        render(bad)


# --------------------------------------------------------------- D9.0 carry-overs
def test_forecast_report_shows_live_searched_caveat() -> None:
    record = _load("forecast_record.json")
    record["live_searched"] = True
    html = render(record)
    assert "Live-searched inputs" in html
    assert 'class="caveat"' in html


def test_snippetless_fetched_source_is_labeled_retrieved_not_cited() -> None:
    draft = _load("draft_searched.json")
    for s in draft["sources_fetched"]:
        s["snippet"] = ""  # a source Claude fetched but never quoted
    html = render(draft)
    assert "retrieved, not cited" in html


def test_advise_report_has_sections_and_caveat() -> None:
    html = render(_load("advise.json"))
    for heading in ("Baseline actor map", "Own moves", "Top own moves", "Who to work on"):
        assert heading in html
    assert "One-sided search" in html  # the standing caveat
    assert 'class="caveat"' in html
    assert "advising <strong>germany" in html
    assert ">play</th>" in html and "energize" in html  # D8.0b energize/defuse labels
