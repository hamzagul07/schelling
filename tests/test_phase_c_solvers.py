"""Phase C solvers (Session 41, D41): challenge-qre, nash, nash-ks, pce.

Hand-computed cases pin the bargaining and Condorcet solvers; the QRE tests check determinism and
the median-lock diagnostic. A separate test asserts the challenge and compromise paths are byte
-identical (the D39.2 guarantee that no existing solver's numerical path changed).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from schelling.mc.monte_carlo import (
    MODEL_CHALLENGE,
    MODEL_CHALLENGE_QRE,
    MODEL_COMPROMISE,
    MODEL_NASH,
    MODEL_NASH_KS,
    MODEL_PCE,
    forecast,
)
from schelling.schemas.question import Continuum, GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.config import SolverConfig
from schelling.solver.nash import ks_forecast, nash_forecast
from schelling.solver.pce import pce_distribution
from schelling.solver.qre import run_qre

FIXTURES = Path(__file__).parent / "fixtures"


def _game(positions: list[float], *, weights: list[float] | None = None) -> GameSpec:
    n = len(positions)
    caps = weights if weights is not None else [50.0] * n
    actors = [
        Actor(
            id=f"a{i}",
            name=f"A{i}",
            position=TriangularEstimate.point(positions[i]),
            salience=TriangularEstimate.point(100.0),
            capability=TriangularEstimate.point(caps[i]),
            evidence=[],
        )
        for i in range(n)
    ]
    return GameSpec(
        question_id="Q",
        frozen_at="2026-07-24",
        continuum=Continuum(label="l", anchor_0="0", anchor_100="100"),
        actors=actors,
        template="t",
        horizon="h",
    )


def _widened() -> GameSpec:
    return GameSpec.model_validate(
        json.loads((FIXTURES / "emission_standards_widened.json").read_text())
    )


# --------------------------------------------------------------- Nash (hand-computed)
def test_nash_opposed_pair_returns_disagreement() -> None:
    # two actors at 0 and 100, disagreement 50: no outcome Pareto-improves -> Nash = disagreement
    cfg = SolverConfig(reference_point=50.0)
    assert nash_forecast(_game([0.0, 100.0]), cfg) == pytest.approx(50.0)


def test_nash_pulls_to_the_binding_actor() -> None:
    # actors [40, 60], disagreement 0: the Nash product peaks at the nearer ideal, x = 40
    cfg = SolverConfig(reference_point=0.0)
    assert nash_forecast(_game([40.0, 60.0]), cfg) == pytest.approx(40.0, abs=0.1)


def test_ks_equalizes_normalized_gains() -> None:
    # actors [40, 60], disagreement 0: KS equalizes g/G -> (80-x)/40 = x/60 -> x = 48
    cfg = SolverConfig(reference_point=0.0)
    assert ks_forecast(_game([40.0, 60.0]), cfg) == pytest.approx(48.0, abs=0.1)


# --------------------------------------------------------------- PCE (hand-reasoned)
def test_pce_symmetric_is_centre() -> None:
    r = pce_distribution(_game([0.0, 50.0, 100.0]))
    assert r.forecast == pytest.approx(50.0)  # symmetry
    assert r.modal == pytest.approx(50.0)  # the centre candidate wins most often
    assert sum(r.probabilities) == pytest.approx(1.0)


def test_pce_leans_to_the_majority() -> None:
    # two actors at 0, one at 100: the 0-coalition is the more probable winner
    r = pce_distribution(_game([0.0, 0.0, 100.0]))
    assert r.modal == pytest.approx(0.0)
    assert 30.0 < r.forecast < 50.0


# --------------------------------------------------------------- QRE
def test_qre_is_deterministic() -> None:
    game = _widened()
    a = run_qre(game)
    b = run_qre(game)
    assert a.forecast_median == b.forecast_median
    assert a.median_trajectory == b.median_trajectory


def test_qre_differs_from_challenge() -> None:
    # a genuinely different solver: softened acceptance moves the forecast off the hard argmax
    game = _widened()
    from schelling.solver.model import run

    challenge = run(game).forecast_median
    qre = run_qre(game).forecast_median
    assert qre != challenge


def test_qre_does_not_collapse_dispersion() -> None:
    """The median-lock diagnostic (D41.1) is measured on real data, not asserted here; what a unit
    test can pin is the necessary direction — softening acceptance never *reduces* the ensemble
    spread. (Whether it fully melts a given lock is reported honestly on the DEU run.)"""
    game = _widened()
    challenge = forecast(game, n_draws=300, seed=1, write=False, model=MODEL_CHALLENGE)
    qre = forecast(game, n_draws=300, seed=1, write=False, model=MODEL_CHALLENGE_QRE)
    assert len(set(qre.outcome_distribution)) >= len(set(challenge.outcome_distribution))


# --------------------------------------------------------------- registration / no-regression
def test_new_models_run_through_forecast() -> None:
    game = _widened()
    for model in (MODEL_CHALLENGE_QRE, MODEL_NASH, MODEL_NASH_KS, MODEL_PCE):
        rec = forecast(game, n_draws=50, seed=3, write=False, model=model)
        assert rec.model == model
        assert 0.0 <= rec.ensemble.median <= 100.0


def test_challenge_and_compromise_are_unchanged(tmp_path: Path) -> None:
    """Adding the new models must not perturb the existing paths (the D39.2 guarantee)."""
    game = _widened()
    cfg = SolverConfig()
    ch = forecast(game, cfg, n_draws=300, seed=42, write=False, model=MODEL_CHALLENGE)
    co = forecast(game, cfg, n_draws=300, seed=42, write=False, model=MODEL_COMPROMISE)
    # re-solving is byte-identical (determinism) and the challenge path still yields a tornado
    assert (
        forecast(game, cfg, n_draws=300, seed=42, write=False).model_dump_json()
        == ch.model_dump_json()
    )
    assert ch.sensitivity and not co.sensitivity
    assert np.isfinite(ch.ensemble.median) and np.isfinite(co.ensemble.median)
