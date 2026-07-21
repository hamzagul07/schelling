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


def test_render_is_deterministic() -> None:
    data = _load("forecast_record.json")
    assert render(data) == render(data)


# --------------------------------------------------------------- offline / self-contained
@pytest.mark.parametrize("name", ["forecast_record.json", "draft.json", "advise.json"])
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
def test_advise_report_has_sections_and_caveat() -> None:
    html = render(_load("advise.json"))
    for heading in ("Baseline actor map", "Own moves", "Top own moves", "Who to work on"):
        assert heading in html
    assert "One-sided search" in html  # the standing caveat
    assert 'class="caveat"' in html
    assert "advising <strong>germany" in html
