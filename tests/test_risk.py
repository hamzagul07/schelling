"""Tests for risk propensity (BUILD_PLAN §4 step 5; Scholz §5, eqs. 32-34, 33)."""

from __future__ import annotations

import numpy as np
import pytest

from schelling.solver.risk import risk_basis, risk_exponents, security_levels


def test_security_adversary_is_column_sum() -> None:
    # eu[c, r] = challenger c's EU of challenging r; adversary security of r = column r.
    eu = np.array([[0.0, 1.0, 2.0], [3.0, 0.0, 4.0], [5.0, 6.0, 0.0]])
    np.testing.assert_allclose(security_levels(eu, "adversary"), [8.0, 7.0, 6.0])


def test_security_own_is_row_sum() -> None:
    eu = np.array([[0.0, 1.0, 2.0], [3.0, 0.0, 4.0], [5.0, 6.0, 0.0]])
    np.testing.assert_allclose(security_levels(eu, "own"), [3.0, 7.0, 11.0])


def test_risk_basis_maps_to_minus_one_zero_plus_one() -> None:
    # security [1, 2, 3] -> R_i = s - 2 -> [-1, 0, 1]
    np.testing.assert_allclose(risk_basis(np.array([1.0, 2.0, 3.0])), [-1.0, 0.0, 1.0])


def test_risk_basis_degenerate_when_all_equal() -> None:
    np.testing.assert_allclose(risk_basis(np.array([5.0, 5.0, 5.0])), [0.0, 0.0, 0.0])


def test_risk_exponents_endpoints() -> None:
    # R_i = -1 -> r = 2 (risk-acceptant); 0 -> 1; +1 -> 0.5 (risk-averse)
    np.testing.assert_allclose(risk_exponents(np.array([-1.0, 0.0, 1.0])), [2.0, 1.0, 0.5])


def test_most_secure_actor_is_most_risk_acceptant() -> None:
    security = np.array([10.0, 5.0, 1.0])  # actor 2 least challenged -> most secure
    r = risk_exponents(risk_basis(security))
    assert r[2] == pytest.approx(2.0)  # most secure -> r = 2
    assert r[0] == pytest.approx(0.5)  # least secure -> r = 0.5
