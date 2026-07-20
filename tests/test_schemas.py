"""Tests for the pydantic v2 data contracts (BUILD_PLAN §3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schelling.schemas.forecast import SolverResult, StoppingRule
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate


def test_triangular_point_is_degenerate() -> None:
    t = TriangularEstimate.point(62.0)
    assert (t.low, t.mode, t.high) == (62.0, 62.0, 62.0)
    assert t.is_point


def test_triangular_rejects_out_of_order() -> None:
    with pytest.raises(ValidationError, match="low <= mode <= high"):
        TriangularEstimate(low=70, mode=62, high=55)


def test_triangular_range_is_not_a_point() -> None:
    assert not TriangularEstimate(low=55, mode=62, high=70).is_point


def test_actor_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Actor(
            id="x",
            name="X",
            position=TriangularEstimate.point(1),
            salience=TriangularEstimate.point(1),
            capability=TriangularEstimate.point(1),
            bogus=123,  # type: ignore[call-arg]
        )


def test_gamespec_requires_at_least_one_actor() -> None:
    with pytest.raises(ValidationError):
        GameSpec(
            question_id="Q",
            frozen_at="2026-01-01",
            continuum={"label": "l", "anchor_0": "a", "anchor_100": "b"},  # type: ignore[arg-type]
            actors=[],
            template="t",
            horizon="one_shot",
        )


def test_toy_fixture_round_trips(toy_game: GameSpec) -> None:
    assert toy_game.question_id == "Q-TOY-3ACTOR"
    assert len(toy_game.actors) == 3
    # canonical JSON round-trip is stable (relied on for inputs_hash later)
    assert GameSpec.model_validate_json(toy_game.model_dump_json()) == toy_game


def test_solver_result_is_frozen() -> None:
    result = SolverResult(
        rounds=[],
        rounds_executed=0,
        stopping_rule=StoppingRule.CONVERGED,
        forecast_median=20.0,
        forecast_mean=27.69,
    )
    with pytest.raises(ValidationError):
        result.forecast_median = 1.0  # type: ignore[misc]
