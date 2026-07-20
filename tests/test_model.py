"""Tests for solver orchestration (BUILD_PLAN §4; the pure run(game, config) contract)."""

from __future__ import annotations

from schelling.schemas.forecast import SolverResult, StoppingRule
from schelling.schemas.question import GameSpec
from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.model import run


def test_run_returns_populated_solver_result(toy_game: GameSpec) -> None:
    result = run(toy_game, SolverConfig(range_mode=RangeMode.FIXED, fixed_range=100.0))
    assert isinstance(result, SolverResult)
    assert result.rounds_executed == len(result.rounds) >= 1
    first = result.rounds[0]
    # RoundLog fully populated: a position per actor, and a relation for every ordered pair.
    assert set(first.positions.keys()) == {a.id for a in toy_game.actors}
    assert first.octant_matrix  # non-empty relation matrix
    total_relations = sum(len(v) for v in first.octant_matrix.values())
    assert total_relations == 3  # C(3,2) unordered pairs


def test_run_is_deterministic(toy_game: GameSpec) -> None:
    cfg = SolverConfig(range_mode=RangeMode.FIXED, fixed_range=100.0)
    assert run(toy_game, cfg).model_dump_json() == run(toy_game, cfg).model_dump_json()


def test_run_forecast_matches_last_round(toy_game: GameSpec) -> None:
    result = run(toy_game, SolverConfig(range_mode=RangeMode.FIXED, fixed_range=100.0))
    assert result.forecast_median == result.rounds[-1].weighted_median
    assert result.forecast_mean == result.rounds[-1].weighted_mean


def test_run_respects_round_cap(toy_game: GameSpec) -> None:
    # An impossible convergence threshold forces the hard cap to fire.
    cfg = SolverConfig(
        range_mode=RangeMode.FIXED, fixed_range=100.0, max_rounds=5, convergence_epsilon=-1.0
    )
    result = run(toy_game, cfg)
    assert result.rounds_executed == 5
    assert result.stopping_rule == StoppingRule.ROUND_CAP


def test_run_defaults_to_a_config_when_none(toy_game: GameSpec) -> None:
    result = run(toy_game)
    assert result.rounds_executed >= 1
