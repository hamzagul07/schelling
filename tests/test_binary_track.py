"""Crowd-baseline binary track (Session 47, D47): the derived binary probability, the band-to-binary
mapping requirement, Brier on a hand-checked fixture, and track separation from the continuum track.
"""

from __future__ import annotations

import pytest

from schelling.backtest.scoring import (
    binary_prob_met,
    binary_realized,
    binary_track,
    brier_binary,
)
from schelling.evidence.metaculus import MetaculusMatch, build_crowd_record
from schelling.schemas.forecast import Ensemble, ForecastRecord
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor, TriangularEstimate

_BANDS = [
    RubricBand(lo=0.0, hi=33.0, label="low"),
    RubricBand(lo=34.0, hi=66.0, label="mid"),
    RubricBand(lo=67.0, hi=100.0, label="high"),
]


def _rubric(met: list[str]) -> ResolutionRubric:
    return ResolutionRubric(
        resolution_criteria="c",
        adjudicating_sources=["s"],
        outcome_mapping="m",
        grading_formula="f",
        bands=_BANDS,
        binary_met_bands=met,
    )


def _game(rubric: ResolutionRubric) -> GameSpec:
    return GameSpec(
        question_id="Q",
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
        resolution_rubric=rubric,
    )


def _record(game: GameSpec, draws: list[float], median: float) -> ForecastRecord:
    return ForecastRecord(
        question_id="Q",
        run_id="r",
        inputs_hash="h",
        seed=0,
        ensemble=Ensemble(
            median=median, mean=median, p10=min(draws), p90=max(draws), n_draws=len(draws)
        ),
        game=game,
        outcome_distribution=list(draws),
    )


# draws: 2 low (10), 5 mid (50), 3 high (80) -> band shares 0.2 / 0.5 / 0.3
_DRAWS = [10.0] * 2 + [50.0] * 5 + [80.0] * 3


def test_binary_prob_met_is_the_declared_met_band_share() -> None:
    rec = _record(_game(_rubric(["high"])), _DRAWS, 50.0)
    assert binary_prob_met(rec, _rubric(["high"])) == pytest.approx(0.3)  # high share
    assert binary_prob_met(rec, _rubric(["mid", "high"])) == pytest.approx(0.8)  # mid + high


def test_binary_prob_met_none_when_mapping_undeclared() -> None:
    rec = _record(_game(_rubric([])), _DRAWS, 50.0)
    assert binary_prob_met(rec, _rubric([])) is None  # no binary_met_bands -> no binary track
    assert binary_realized(80.0, _rubric([])) is None


def test_binary_realized_from_actual() -> None:
    rubric = _rubric(["high"])
    assert binary_realized(80.0, rubric) is True  # 80 -> high (met)
    assert binary_realized(50.0, rubric) is False  # 50 -> mid (not met)
    assert binary_realized(20.0, rubric) is False  # 20 -> low (not met)


def test_brier_binary_by_hand() -> None:
    assert brier_binary(0.7, True) == pytest.approx(0.09)  # (0.7 - 1)^2
    assert brier_binary(0.7, False) == pytest.approx(0.49)  # (0.7 - 0)^2
    assert brier_binary(1.0, True) == pytest.approx(0.0)
    assert brier_binary(0.0, False) == pytest.approx(0.0)


def test_binary_track_scores_solver_and_crowd_and_stays_separate() -> None:
    rubric = _rubric(["high"])
    game = _game(rubric)
    solver = _record(game, [80.0] * 10, 80.0)  # all high -> P(met) = 1.0
    crowd = build_crowd_record(
        game,
        MetaculusMatch(
            metaculus_id=1,
            title="t",
            url="u",
            community_prediction=0.7,
            n_forecasters=50,
            close_time="",
        ),
        placement=70.0,
        justification="a genuine match",
    )
    scores = binary_track([solver], [crowd], {"Q": 80.0}, lambda _q: rubric)  # actual 80 -> met
    by_model = {s.model: s for s in scores}
    assert by_model["challenge"].brier == pytest.approx(0.0)  # P(met)=1, met -> 0
    assert by_model["crowd-metaculus"].brier == pytest.approx(0.09)  # (0.7-1)^2
    assert by_model["crowd-metaculus"].p_met == pytest.approx(0.7)
    # the binary track carries only P(met)/Brier — never a |median - actual| continuum score
    assert all(s.realized_met for s in scores)


def test_binary_track_empty_without_declared_mapping() -> None:
    # a question with no binary_met_bands contributes nothing to the binary track
    rubric = _rubric([])
    solver = _record(_game(rubric), _DRAWS, 50.0)
    assert binary_track([solver], [], {"Q": 80.0}, lambda _q: rubric) == []


def test_crowd_baseline_requires_the_band_to_binary_mapping() -> None:
    game = _game(_rubric([]))  # rubric declares no binary_met_bands
    with pytest.raises(ValueError, match="binary_met_bands"):
        build_crowd_record(
            game,
            MetaculusMatch(
                metaculus_id=1,
                title="t",
                url="u",
                community_prediction=0.7,
                n_forecasters=50,
                close_time="",
            ),
            placement=70.0,
            justification="ok",
        )
