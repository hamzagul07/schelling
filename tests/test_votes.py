"""Unit tests for the vote layer (BUILD_PLAN §4 steps 1-3).

The toy 3-actor game has hand-computable answers:

    weights:  A = 40*50/100 = 20,  B = 100*80/100 = 80,  C = 50*60/100 = 30
    mean:     (20*10 + 80*20 + 30*60) / 130 = 3600/130 = 27.692307...
    median:   cumulative weight crosses 65 at B's position -> 20 (B is the median voter)

Continuum range R = 100 throughout (the 0-100 policy scale).
"""

from __future__ import annotations

import numpy as np
import pytest

from schelling.schemas.question import GameSpec
from schelling.solver.votes import (
    contest_matrix,
    effective_weights,
    game_mode_arrays,
    net_votes,
    weighted_mean,
    weighted_median,
)

R = 100.0

# Toy game arrays (positions, saliences, capabilities), actor order A, B, C.
TOY_POSITIONS = np.array([10.0, 20.0, 60.0])
TOY_SALIENCE = np.array([50.0, 80.0, 60.0])
TOY_CAPABILITY = np.array([40.0, 100.0, 50.0])
TOY_WEIGHTS = np.array([20.0, 80.0, 30.0])


# --------------------------------------------------------------------------- weights
def test_effective_weights_toy() -> None:
    w = effective_weights(TOY_CAPABILITY, TOY_SALIENCE)
    np.testing.assert_allclose(w, TOY_WEIGHTS)


def test_effective_weights_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same shape"):
        effective_weights(np.array([1.0, 2.0]), np.array([1.0]))


def test_effective_weights_equal_saliences_are_proportional_to_capability() -> None:
    cap = np.array([10.0, 20.0, 40.0])
    sal = np.array([70.0, 70.0, 70.0])
    w = effective_weights(cap, sal)
    # equal salience => weights are a constant multiple of capability
    ratios = w / cap
    np.testing.assert_allclose(ratios, ratios[0])


# --------------------------------------------------------------------------- mean
def test_weighted_mean_toy() -> None:
    assert weighted_mean(TOY_POSITIONS, TOY_WEIGHTS) == pytest.approx(3600.0 / 130.0)


def test_weighted_mean_single_actor_is_its_position() -> None:
    assert weighted_mean(np.array([42.0]), np.array([24.0])) == pytest.approx(42.0)


def test_weighted_mean_zero_total_weight_raises() -> None:
    with pytest.raises(ValueError, match="total weight is zero"):
        weighted_mean(TOY_POSITIONS, np.zeros(3))


# --------------------------------------------------------------------------- median
def test_weighted_median_toy_is_median_voter() -> None:
    assert weighted_median(TOY_POSITIONS, TOY_WEIGHTS) == pytest.approx(20.0)


def test_weighted_median_single_actor_is_its_position() -> None:
    assert weighted_median(np.array([42.0]), np.array([24.0])) == pytest.approx(42.0)


def test_weighted_median_tie_takes_lower_position() -> None:
    # Two equal-weight actors astride the midpoint: cumulative weight hits half exactly
    # at the lower position. The lower weighted median convention returns it deterministically.
    positions = np.array([10.0, 30.0])
    weights = np.array([50.0, 50.0])
    assert weighted_median(positions, weights) == pytest.approx(10.0)


def test_weighted_median_zero_total_weight_raises() -> None:
    with pytest.raises(ValueError, match="total weight is zero"):
        weighted_median(TOY_POSITIONS, np.zeros(3))


def test_weighted_median_dominant_actor_pulls_forecast_to_itself() -> None:
    # One actor holding a majority of the weight is itself the median voter.
    positions = np.array([5.0, 50.0, 95.0])
    weights = np.array([10.0, 200.0, 10.0])
    assert weighted_median(positions, weights) == pytest.approx(50.0)


# --------------------------------------------------------------------------- contests
def test_net_votes_median_defeats_both_alternatives() -> None:
    # 20 vs 10 -> +900/R ; 20 vs 60 -> +2800/R ; both positive => 20 wins each contest.
    assert net_votes(TOY_POSITIONS, TOY_WEIGHTS, 20.0, 10.0, R) == pytest.approx(9.0)
    assert net_votes(TOY_POSITIONS, TOY_WEIGHTS, 20.0, 60.0, R) == pytest.approx(28.0)


def test_net_votes_is_antisymmetric() -> None:
    forward = net_votes(TOY_POSITIONS, TOY_WEIGHTS, 20.0, 60.0, R)
    reverse = net_votes(TOY_POSITIONS, TOY_WEIGHTS, 60.0, 20.0, R)
    assert forward == pytest.approx(-reverse)


def test_net_votes_equal_positions_is_zero() -> None:
    assert net_votes(TOY_POSITIONS, TOY_WEIGHTS, 33.0, 33.0, R) == pytest.approx(0.0)


def test_net_votes_nonpositive_range_raises() -> None:
    with pytest.raises(ValueError, match="continuum_range must be positive"):
        net_votes(TOY_POSITIONS, TOY_WEIGHTS, 20.0, 10.0, 0.0)


def test_contest_matrix_is_antisymmetric_with_zero_diagonal() -> None:
    m = contest_matrix(TOY_POSITIONS, TOY_POSITIONS, TOY_WEIGHTS, R)
    np.testing.assert_allclose(np.diag(m), 0.0)
    np.testing.assert_allclose(m, -m.T)


def test_contest_matrix_elects_the_weighted_median_as_condorcet_winner() -> None:
    candidates = TOY_POSITIONS
    m = contest_matrix(candidates, TOY_POSITIONS, TOY_WEIGHTS, R)
    # A Condorcet winner's row is non-negative against every alternative.
    winners = [i for i in range(len(candidates)) if np.all(m[i] >= 0.0)]
    assert len(winners) == 1
    assert candidates[winners[0]] == pytest.approx(weighted_median(TOY_POSITIONS, TOY_WEIGHTS))


def test_contest_matrix_matches_net_votes_pairwise() -> None:
    m = contest_matrix(TOY_POSITIONS, TOY_POSITIONS, TOY_WEIGHTS, R)
    for a in range(3):
        for b in range(3):
            expected = net_votes(TOY_POSITIONS, TOY_WEIGHTS, TOY_POSITIONS[a], TOY_POSITIONS[b], R)
            assert m[a, b] == pytest.approx(expected)


def test_single_actor_contest_is_degenerate() -> None:
    positions = np.array([42.0])
    weights = np.array([24.0])
    m = contest_matrix(positions, positions, weights, R)
    assert m.shape == (1, 1)
    assert m[0, 0] == pytest.approx(0.0)


# --------------------------------------------------------------------------- fixture wiring
def test_game_mode_arrays_from_toy_fixture(toy_game: GameSpec) -> None:
    positions, saliences, capabilities = game_mode_arrays(toy_game)
    np.testing.assert_allclose(positions, TOY_POSITIONS)
    np.testing.assert_allclose(saliences, TOY_SALIENCE)
    np.testing.assert_allclose(capabilities, TOY_CAPABILITY)


def test_end_to_end_forecast_from_fixture(toy_game: GameSpec) -> None:
    positions, saliences, capabilities = game_mode_arrays(toy_game)
    weights = effective_weights(capabilities, saliences)
    np.testing.assert_allclose(weights, TOY_WEIGHTS)
    assert weighted_mean(positions, weights) == pytest.approx(3600.0 / 130.0)
    assert weighted_median(positions, weights) == pytest.approx(20.0)
