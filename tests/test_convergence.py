"""Tests for the stopping rule (BUILD_PLAN §4 step 8)."""

from __future__ import annotations

import pytest

from schelling.solver.convergence import has_converged


def test_not_converged_before_enough_rounds() -> None:
    assert has_converged([7.0, 7.0], epsilon=0.5, patience=2) is False


def test_converged_when_two_moves_below_epsilon() -> None:
    assert has_converged([7.0, 7.2, 7.3], epsilon=0.5, patience=2) is True


def test_not_converged_when_a_recent_move_exceeds_epsilon() -> None:
    assert has_converged([7.0, 8.0, 8.1], epsilon=0.5, patience=2) is False


def test_boundary_move_equal_to_epsilon_is_not_below() -> None:
    # a move of exactly epsilon does not count as "< epsilon"
    assert has_converged([0.0, 0.5, 0.5], epsilon=0.5, patience=2) is False


def test_single_move_patience() -> None:
    assert has_converged([9.9, 9.9], epsilon=0.5, patience=1) is True
    assert has_converged([9.0, 9.9], epsilon=0.5, patience=1) is False


def test_only_the_last_patience_moves_matter() -> None:
    # early big jumps are ignored once the tail settles
    assert has_converged([0.0, 5.0, 9.9, 9.9, 9.9], epsilon=0.5, patience=2) is True


def test_invalid_patience_raises() -> None:
    with pytest.raises(ValueError, match="patience must be >= 1"):
        has_converged([1.0, 2.0], epsilon=0.5, patience=0)
