"""Tests for the round mechanics (BUILD_PLAN §4 step 7)."""

from __future__ import annotations

import numpy as np

from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.octants import Offer, Relation
from schelling.solver.rounds import _select_offer, continuum_range, run_round


def test_continuum_range_dynamic_is_max_minus_min() -> None:
    positions = np.array([4.0, 7.0, 10.0])
    cfg = SolverConfig(range_mode=RangeMode.DYNAMIC)
    assert continuum_range(positions, cfg) == 6.0


def test_continuum_range_fixed_ignores_positions() -> None:
    positions = np.array([4.0, 7.0, 10.0])
    cfg = SolverConfig(range_mode=RangeMode.FIXED, fixed_range=100.0)
    assert continuum_range(positions, cfg) == 100.0


def test_continuum_range_dynamic_degenerate_is_zero() -> None:
    positions = np.array([5.0, 5.0, 5.0])
    assert continuum_range(positions, SolverConfig(range_mode=RangeMode.DYNAMIC)) == 0.0


def test_select_offer_prefers_higher_enforceability() -> None:
    positions = np.array([4.0, 7.0])
    offers = [
        Offer(Relation.COMPEL, mover=0, new_position=10.0, enforceability=0.3),
        Offer(Relation.COMPROMISE, mover=0, new_position=6.0, enforceability=0.9),
    ]
    # Actor 0 accepts the more enforceable (0.9) offer even though it is not the smaller move.
    assert _select_offer(offers, positions) == {0: 6.0}


def test_select_offer_ties_break_to_least_move() -> None:
    positions = np.array([5.0])
    offers = [
        Offer(Relation.COMPEL, mover=0, new_position=9.0, enforceability=0.5),
        Offer(Relation.COMPEL, mover=0, new_position=6.0, enforceability=0.5),
    ]
    assert _select_offer(offers, positions) == {0: 6.0}  # |6-5| < |9-5|


def test_select_offer_ignores_no_move_offers() -> None:
    positions = np.array([5.0, 5.0])
    offers = [Offer(Relation.STATUS_QUO, mover=None, new_position=None)]
    assert _select_offer(offers, positions) == {}


def test_run_round_all_equal_positions_no_move() -> None:
    positions = np.array([5.0, 5.0, 5.0])
    saliences = np.array([50.0, 60.0, 70.0])
    cs = np.array([1.0, 2.0, 3.0])
    outcome = run_round(positions, saliences, cs, SolverConfig())
    np.testing.assert_allclose(outcome.new_positions, positions)
    assert outcome.accepted_offers == {}


def test_run_round_is_deterministic_and_records_all_pairs() -> None:
    positions = np.array([4.0, 7.0, 10.0])
    saliences = np.array([80.0, 40.0, 90.0])
    cs = np.array([0.5, 0.3, 0.9])
    cfg = SolverConfig()
    a = run_round(positions, saliences, cs, cfg)
    b = run_round(positions, saliences, cs, cfg)
    np.testing.assert_array_equal(a.new_positions, b.new_positions)
    # every unordered pair is classified
    assert set(a.relations.keys()) == {(0, 1), (0, 2), (1, 2)}
    assert a.new_positions.shape == positions.shape
