"""Tests for octant classification and offers (BUILD_PLAN §4 step 6; Scholz §6, eqs. 35-36)."""

from __future__ import annotations

import pytest

from schelling.solver.octants import Relation, classify


def test_conflict_resolves_lower_eu_concedes_fully() -> None:
    # a > b > 0: j (lower... no, a=E^i>b=E^j) -> j concedes to x_i.
    off = classify(a=2.0, b=1.0, i=0, j=1, x_i=10.0, x_j=4.0, conflict_resolves=True)
    assert off.relation is Relation.CONFLICT
    assert off.mover == 1 and off.new_position == pytest.approx(10.0)
    assert off.enforceability == pytest.approx(2.0)


def test_conflict_can_be_no_move() -> None:
    off = classify(a=2.0, b=1.0, i=0, j=1, x_i=10.0, x_j=4.0, conflict_resolves=False)
    assert off.relation is Relation.CONFLICT
    assert off.mover is None and off.new_position is None


def test_conflict_equal_eu_is_stalemate() -> None:
    off = classify(a=1.5, b=1.5, i=0, j=1, x_i=10.0, x_j=4.0, conflict_resolves=True)
    assert off.relation is Relation.STALEMATE
    assert off.mover is None


def test_compromise_plus_moves_j_part_way_to_i() -> None:
    # a>0, b<0, |a|>|b|: j moves part way to i. x_hat = (10-4)*|(-1)/2| = 3 -> new x_j = 7.
    off = classify(a=2.0, b=-1.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert off.relation is Relation.COMPROMISE
    assert off.mover == 1 and off.new_position == pytest.approx(7.0)


def test_compel_plus_moves_j_fully_to_i() -> None:
    # a>0, b<0, |b|>|a|: j moves fully to i.
    off = classify(a=1.0, b=-2.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert off.relation is Relation.COMPEL
    assert off.mover == 1 and off.new_position == pytest.approx(10.0)


def test_compromise_minus_moves_i_part_way_to_j() -> None:
    # a<0, b>0, |b|>|a|: i moves part way to j. x_hat = (10-4)*|(-1)/2| = 3 -> new x_i = 7.
    off = classify(a=-1.0, b=2.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert off.relation is Relation.COMPROMISE
    assert off.mover == 0 and off.new_position == pytest.approx(7.0)


def test_compel_minus_moves_i_fully_to_j() -> None:
    off = classify(a=-2.0, b=1.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert off.relation is Relation.COMPEL
    assert off.mover == 0 and off.new_position == pytest.approx(4.0)


def test_both_negative_is_status_quo() -> None:
    off = classify(a=-1.0, b=-2.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert off.relation is Relation.STATUS_QUO
    assert off.mover is None


def test_compromise_ratio_endpoints() -> None:
    # ratio -> 1: full move; ratio -> 0: no move.
    full = classify(a=2.0, b=-2.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert full.new_position == pytest.approx(10.0)  # x_j + (10-4)*1
    tiny = classify(a=100.0, b=-1.0, i=0, j=1, x_i=10.0, x_j=4.0)
    assert tiny.new_position == pytest.approx(4.06)  # x_j + (10-4)*0.01
