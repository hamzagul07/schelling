"""Tests for basic utilities, prevail probability, and expected utility (Scholz §3-4)."""

from __future__ import annotations

import numpy as np
import pytest

from schelling.solver.expected_utility import (
    basic_utilities,
    expected_utility,
    prevail_probability,
    t_indicator,
)


def test_basic_utilities_at_zero_distance_are_equal_at_r_one() -> None:
    # x_i == x_j == mu, r = 1: every base is 0.5, so all utilities equal 2 - 4*0.5 = 0.
    u = basic_utilities(x_i=5.0, x_j=5.0, mu=5.0, cont_range=6.0, r=1.0)
    assert u.u_s == pytest.approx(0.0)
    assert u.u_f == pytest.approx(0.0)
    assert u.u_sq == pytest.approx(0.0)
    assert u.u_b == pytest.approx(0.0)
    assert u.u_w == pytest.approx(0.0)


def test_basic_utilities_success_beats_failure() -> None:
    # At maximum distance (d=1), success U_s = 2, failure U_f = -2 (r=1).
    u = basic_utilities(x_i=4.0, x_j=10.0, mu=7.0, cont_range=6.0, r=1.0)
    assert u.u_s == pytest.approx(2.0)
    assert u.u_f == pytest.approx(-2.0)
    assert u.u_s > u.u_f


def test_basic_utilities_reject_nonpositive_range() -> None:
    with pytest.raises(ValueError, match="cont_range must be positive"):
        basic_utilities(1.0, 2.0, 1.5, 0.0, 1.0)


def test_prevail_probability_symmetric_is_half() -> None:
    positions = np.array([0.0, 10.0])
    weights = np.array([1.0, 1.0])
    assert prevail_probability(0.0, 10.0, positions, weights) == pytest.approx(0.5)


def test_prevail_probability_majority_support() -> None:
    # Two voters at i's position (0), one at j's (10): support 20 of 30 total -> 2/3.
    positions = np.array([0.0, 0.0, 10.0])
    weights = np.array([1.0, 1.0, 1.0])
    assert prevail_probability(0.0, 10.0, positions, weights) == pytest.approx(2.0 / 3.0)


def test_prevail_probability_all_equidistant_is_half() -> None:
    positions = np.array([5.0, 5.0])  # equidistant from 0 and 10
    weights = np.array([1.0, 1.0])
    assert prevail_probability(0.0, 10.0, positions, weights) == pytest.approx(0.5)


def test_t_indicator_selects_better_when_median_closer() -> None:
    assert t_indicator(x_i=4.0, x_j=10.0, mu=6.0) == 1.0  # |4-6|=2 < |4-10|=6
    assert t_indicator(x_i=4.0, x_j=10.0, mu=12.0) == 0.0  # |4-12|=8 > 6


def test_expected_utility_positive_when_challenger_dominates() -> None:
    # A large supporting coalition and a low-salience target -> positive EU of challenging.
    positions = np.array([0.0, 0.0, 0.0, 10.0])
    saliences = np.array([50.0, 50.0, 50.0, 10.0])
    cs = np.array([1.0, 1.0, 1.0, 1.0])
    e = expected_utility(
        challenger=0,
        responder=3,
        positions=positions,
        saliences=saliences,
        cs_weights=cs,
        mu=0.0,
        cont_range=10.0,
        r_challenger=1.0,
        q=1.0,
    )
    assert e > 0.0
