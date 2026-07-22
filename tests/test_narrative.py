"""Two-audience narrative report (Session 22): band mapping, layered sections, determinism.

Covers the band-probability arithmetic against a hand-computed fixture, the modal/median bands,
the graceful no-rubric and arithmetic/linear paths, verdict text, byte-identical determinism, and
that a rubric-less record still routes to the unchanged standard layout.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from schelling.report import bands as bandmap
from schelling.report.render import (
    _render_forecast_standard,
    render,
    render_forecast,
    render_forecast_narrative,
)
from schelling.report.vocab import load_vocab, phrase_for
from schelling.schemas.forecast import Ensemble, ForecastRecord
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor
from schelling.schemas.stakeholders import TriangularEstimate as T

FIXTURES = Path(__file__).parent / "fixtures"

_BANDS = [
    RubricBand(lo=0, hi=24, label="band A"),
    RubricBand(lo=25, hi=49, label="band B"),
    RubricBand(lo=50, hi=74, label="band C"),
    RubricBand(lo=75, hi=100, label="band D"),
]


def _rubric(bands: list[RubricBand]) -> ResolutionRubric:
    return ResolutionRubric(
        resolution_criteria="x",
        adjudicating_sources=["s"],
        outcome_mapping="map",
        grading_formula="score = |median - actual|",
        bands=bands,
    )


def _game(bands: list[RubricBand] | None) -> GameSpec:
    return GameSpec(
        question_id="Q-T",
        frozen_at="2026-07-22",
        continuum=Continuum(label="sev", anchor_0="low end", anchor_100="high end"),
        template="committee_vote",
        horizon="one decision",
        actors=[
            Actor(
                id="a",
                name="A",
                position=T(low=5, mode=15, high=30),
                salience=T(low=80, mode=90, high=97),
                capability=T(low=90, mode=100, high=100),
            ),
            Actor(
                id="b",
                name="B",
                position=T(low=55, mode=70, high=85),
                salience=T(low=40, mode=55, high=70),
                capability=T(low=40, mode=50, high=60),
            ),
        ],
        resolution_rubric=None if bands is None else _rubric(bands),
    )


def _record(
    draws: Sequence[float], median: float, bands: list[RubricBand] | None
) -> ForecastRecord:
    return ForecastRecord(
        question_id="Q-T",
        run_id="Q-T-mc-s0",
        engine_version="deadbeef",
        inputs_hash="0" * 64,
        seed=0,
        model="challenge",
        ensemble=Ensemble(
            median=median, mean=median, p10=min(draws), p90=max(draws), n_draws=len(draws)
        ),
        game=_game(bands),
        outcome_distribution=list(draws),
    )


# --------------------------------------------------------------- band mapping (item 1)
def test_band_probabilities_sum_to_one_and_match_hand_computed() -> None:
    draws = [10, 10, 10, 30, 30, 60, 90, 90]  # A:3, B:2, C:1, D:2 of 8
    readout = bandmap.map_bands(_record(draws, median=30.0, bands=_BANDS))
    assert readout.kind == bandmap.BANDED
    probs = [bp.probability for bp in readout.per_band]
    assert probs == [3 / 8, 2 / 8, 1 / 8, 2 / 8]
    assert sum(probs) == 1.0


def test_modal_and_median_bands() -> None:
    draws = [10, 10, 10, 30, 30, 60, 90, 90]
    readout = bandmap.map_bands(_record(draws, median=30.0, bands=_BANDS))
    assert readout.modal_band is not None and readout.modal_band.label == "band A"  # 3/8, the mode
    assert readout.median_band is not None and readout.median_band.label == "band B"  # median 30
    modal = [bp for bp in readout.per_band if bp.is_modal]
    median = [bp for bp in readout.per_band if bp.is_median]
    assert [bp.band.label for bp in modal] == ["band A"]
    assert [bp.band.label for bp in median] == ["band B"]


def test_band_membership_uses_lo_threshold_no_gaps() -> None:
    # A float between the written integer bands (e.g. 24.5) still lands cleanly, in band A.
    readout = bandmap.map_bands(_record([24.5, 49.5], median=24.5, bands=_BANDS))
    assert [bp.probability for bp in readout.per_band] == [0.5, 0.5, 0.0, 0.0]


def test_linear_rubric_degrades_to_arithmetic() -> None:
    readout = bandmap.map_bands(_record([10, 40, 80], median=40.0, bands=[]))
    assert readout.kind == bandmap.LINEAR and readout.per_band == []
    assert "arithmetic" in readout.note.lower()


def test_no_rubric_degrades_gracefully() -> None:
    readout = bandmap.map_bands(_record([10, 40, 80], median=40.0, bands=None))
    assert readout.kind == bandmap.NONE and readout.per_band == []
    assert "no resolution rubric" in readout.note.lower()


def test_band_containing_and_none() -> None:
    assert bandmap.band_containing(30.0, _rubric(_BANDS)).label == "band B"  # type: ignore[union-attr]
    assert bandmap.band_containing(30.0, _rubric([])) is None
    assert bandmap.band_containing(30.0, None) is None


def test_compromise_point_matches_advise_settlement() -> None:
    from schelling.advise.search import _compromise_settlement

    g = _game(_BANDS)
    assert bandmap.compromise_point(g) == _compromise_settlement(g)


# --------------------------------------------------------------- narrative render (item 2, 3)
def test_verdict_names_the_modal_band_with_its_probability() -> None:
    draws = [10] * 7 + [90] * 3  # band A modal at 70%
    html = render_forecast_narrative(_record(draws, median=10.0, bands=_BANDS))
    assert "Most likely: <strong>band A</strong> — 70%" in html
    assert (
        "Verdict" in html and "Reading" in html and "Analyst brief" in html and "Appendix" in html
    )


def test_render_is_deterministic_byte_identical() -> None:
    rec = _record([10, 10, 30, 60, 90], median=30.0, bands=_BANDS)
    assert render_forecast_narrative(rec) == render_forecast_narrative(rec)


def test_dispatch_routes_rubric_records_to_narrative() -> None:
    rec = _record([10, 30, 60], median=30.0, bands=_BANDS)
    assert render_forecast(rec) == render_forecast_narrative(rec)
    assert "Verdict" in render_forecast(rec)


def test_dispatch_keeps_standard_layout_for_no_rubric() -> None:
    # A rubric-less record must render byte-identically to the pre-D22 standard layout.
    rec = _record([10, 30, 60], median=30.0, bands=None)
    assert render_forecast(rec) == _render_forecast_standard(rec)


def test_narrative_says_so_when_no_rubric() -> None:
    # Forced onto the narrative path, a rubric-less record explains the missing rubric.
    html = render_forecast_narrative(_record([10, 30, 60], median=30.0, bands=None))
    assert "No resolution rubric is committed" in html


def test_sources_fetched_appear_in_appendix() -> None:
    data = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    html = render(data)
    assert "Sources fetched (2)" in html
    assert "Board adopts June resolution" in html


# --------------------------------------------------------------- golden + vocabulary
def test_narrative_report_matches_golden() -> None:
    data = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    assert render(data) == (FIXTURES / "report" / "forecast_narrative_report.html").read_text()


def test_position_vocabulary_buckets() -> None:
    v = load_vocab()
    assert phrase_for(5, v.position_fifths) == "at the far low end"
    assert phrase_for(50, v.position_fifths) == "close to the midpoint"
    assert phrase_for(95, v.position_fifths) == "at the far high end"
    assert phrase_for(10, v.position_thirds) == "near the low end"
    assert phrase_for(90, v.position_thirds) == "near the high end"
    assert phrase_for(90, v.salience_thirds) == "a defining issue for it"
