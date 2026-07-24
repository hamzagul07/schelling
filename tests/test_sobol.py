"""Sobol global sensitivity (Session 40, D40.3). The estimator is validated against the **Ishigami
function**, whose Sobol indices are known in closed form, so correctness is externally checkable;
the game wrapper is checked for shape, cost, the tornado's parameter set, and determinism.

Ishigami: f(x) = sin(x1) + 7 sin^2(x2) + 0.1 x3^4 sin(x1), each x_i ~ Uniform(-pi, pi). Analytic
first-order S = [0.3139, 0.4424, 0.0]; total-order ST = [0.5574, 0.4424, 0.2437].
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from schelling.mc.sobol import format_sobol, sobol_for_game, sobol_indices
from schelling.schemas.question import GameSpec

FIXTURES = Path(__file__).parent / "fixtures"

ISHIGAMI_S1 = [0.3139, 0.4424, 0.0]
ISHIGAMI_ST = [0.5574, 0.4424, 0.2437]


def _ishigami(x: np.ndarray) -> np.ndarray:
    x1, x2, x3 = x[:, 0], x[:, 1], x[:, 2]
    return np.sin(x1) + 7.0 * np.sin(x2) ** 2 + 0.1 * x3**4 * np.sin(x1)


def _uniform_pi(u01: np.ndarray) -> np.ndarray:
    return -np.pi + 2.0 * np.pi * u01  # map [0,1] -> [-pi, pi]


# --------------------------------------------------------------- estimator vs analytic Ishigami
def test_sobol_estimator_matches_ishigami() -> None:
    res = sobol_indices(_ishigami, _uniform_pi, k=3, n=16384, seed=1)
    assert res.first_order == pytest.approx(ISHIGAMI_S1, abs=0.03)
    assert res.total_order == pytest.approx(ISHIGAMI_ST, abs=0.03)
    # total-order dominates first-order for every parameter (interactions only add variance)
    for s, st in zip(res.first_order, res.total_order, strict=True):
        assert st >= s - 0.02
    # x3 has zero first-order but real total-order — it acts only through its interaction with x1
    assert res.first_order[2] == pytest.approx(0.0, abs=0.03)
    assert res.total_order[2] > 0.15


def test_sobol_cost_is_n_times_2k_plus_2() -> None:
    res = sobol_indices(_ishigami, _uniform_pi, k=3, n=1000, seed=0)
    assert res.cost == 1000 * (2 * 3 + 2)  # N*(2k+2)


def test_sobol_estimator_is_deterministic() -> None:
    a = sobol_indices(_ishigami, _uniform_pi, k=3, n=2048, seed=5)
    b = sobol_indices(_ishigami, _uniform_pi, k=3, n=2048, seed=5)
    assert a.first_order == b.first_order
    assert a.total_order == b.total_order


# --------------------------------------------------------------- the game wrapper
def _widened_game() -> GameSpec:
    return GameSpec.model_validate(
        json.loads((FIXTURES / "emission_standards_widened.json").read_text())
    )


def test_sobol_for_game_compromise_shape_and_determinism() -> None:
    game = _widened_game()
    res = sobol_for_game(game, model="compromise", n=256, seed=3)
    # the ranged parameters are exactly the tornado's set (D40.3)
    assert set(res.labels) == {"france.position", "germany.position"}
    assert res.k == 2 and res.model == "compromise"
    assert res.cost == 256 * (2 * 2 + 2)
    for s, st in zip(res.first_order, res.total_order, strict=True):
        assert -0.05 <= s <= 1.05 and st >= s - 0.05
    again = sobol_for_game(game, model="compromise", n=256, seed=3)
    assert again.first_order == res.first_order and again.total_order == res.total_order


def test_sobol_for_game_point_estimate_has_no_parameters() -> None:
    # the replication fixture is all point estimates -> no ranged parameters, no variance
    game = GameSpec.model_validate(json.loads((FIXTURES / "emission_standards.json").read_text()))
    res = sobol_for_game(game, model="compromise", n=64, seed=0)
    assert res.k == 0
    assert "no ranged parameters" in format_sobol(res)
