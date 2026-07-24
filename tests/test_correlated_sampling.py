"""Correlated input sampling (Session 41, D41.4): opt-in Gaussian copula, committed structure,
identical marginals, and the guarantee that it never changes the default (independent) run.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from schelling.mc.correlated import (
    SALIENCE_RHO,
    salience_cholesky,
    sample_game_correlated,
)
from schelling.mc.monte_carlo import forecast
from schelling.mc.sampling import derive_rng
from schelling.schemas.question import Continuum, GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate

FIXTURES = Path(__file__).parent / "fixtures"


def _widened() -> GameSpec:
    return GameSpec.model_validate(
        json.loads((FIXTURES / "emission_standards_widened.json").read_text())
    )


def _ranged_salience_game() -> GameSpec:
    """Two actors on the same side of the median with ranged salience, plus a far anchor."""

    def actor(aid: str, pos: float, sal: TriangularEstimate) -> Actor:
        return Actor(
            id=aid,
            name=aid,
            position=TriangularEstimate.point(pos),
            salience=sal,
            capability=TriangularEstimate.point(50.0),
            evidence=[],
        )

    sal = TriangularEstimate(low=40.0, mode=60.0, high=80.0)
    return GameSpec(
        question_id="Q",
        frozen_at="2026-07-24",
        continuum=Continuum(label="l", anchor_0="0", anchor_100="100"),
        actors=[
            actor("a", 40.0, sal),
            actor("b", 44.0, sal),
            actor("c", 10.0, TriangularEstimate.point(50.0)),
        ],
        template="t",
        horizon="h",
    )


def test_independent_is_the_default_and_records_it() -> None:
    rec = forecast(_widened(), n_draws=50, seed=1, write=False)
    assert rec.sampling == "independent"


def test_correlated_is_opt_in_and_recorded() -> None:
    rec = forecast(_widened(), n_draws=50, seed=1, write=False, correlated=True)
    assert rec.sampling == "correlated"


def test_correlated_never_changes_the_independent_run() -> None:
    """The opt-in must not silently perturb the default: the independent run is byte-identical
    whether or not the correlated path exists (D41.4)."""
    game = _widened()
    a = forecast(game, n_draws=200, seed=7, write=False)
    b = forecast(game, n_draws=200, seed=7, write=False, correlated=False)
    assert a.model_dump_json() == b.model_dump_json()


def test_correlated_is_deterministic_under_seed() -> None:
    game = _widened()
    a = forecast(game, n_draws=200, seed=7, write=False, correlated=True)
    b = forecast(game, n_draws=200, seed=7, write=False, correlated=True)
    assert a.outcome_distribution == b.outcome_distribution


def test_correlated_changes_the_distribution() -> None:
    # a genuinely different sampler: correlated salience shifts the ensemble off the independent one
    game = _widened()
    ind = forecast(game, n_draws=400, seed=3, write=False)
    cor = forecast(game, n_draws=400, seed=3, write=False, correlated=True)
    assert ind.outcome_distribution != cor.outcome_distribution


def test_marginals_are_preserved_within_a_coalition() -> None:
    """The Gaussian copula keeps each salience's triangular marginal; only the joint changes.

    Two same-coalition actors' salience draws are positively correlated (SALIENCE_RHO > 0), while
    each stays inside its own [low, high] range."""
    game = _ranged_salience_game()
    chol = salience_cholesky(game)
    sal0, sal1 = [], []
    for i in range(2000):
        draw = sample_game_correlated(game, derive_rng(99, i), chol)
        sal0.append(draw.actors[0].salience.mode)
        sal1.append(draw.actors[1].salience.mode)
    a0, a1 = game.actors[0], game.actors[1]
    # marginals respected: every draw is inside the actor's own salience range
    assert all(a0.salience.low <= s <= a0.salience.high for s in sal0)
    assert all(a1.salience.low <= s <= a1.salience.high for s in sal1)
    # actors a and b sit on the same side of the median -> their salience draws are correlated
    assert np.corrcoef(sal0, sal1)[0, 1] > 0.2
    assert 0.0 < SALIENCE_RHO < 1.0
