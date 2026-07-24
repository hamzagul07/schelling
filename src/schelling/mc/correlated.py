"""Correlated input sampling via a Gaussian copula (Session 41, D41.4).

Independent per-field triangular sampling (``mc.sampling.sample_game``) is and stays the default.
This opt-in module draws the same triangular marginals but with a **documented, committed covariance
structure** across actors, so that correlated uncertainty is represented instead of assumed away.

**The committed default structure: salience correlated within coalitions.** Actors on the same side
of the game's capability x salience weighted median (both below it, or both at/above it) form a
coalition; their *salience* draws share a positive correlation ``SALIENCE_RHO`` (fixed below).
Position and capability are drawn independently, as before. The rationale: when an issue heats up,
allies tend to care more together — their saliences move in step — while their ideal points and raw
capabilities do not. The rule is a fixed modelling choice, committed here in code, not fitted.

Mechanics: build the salience correlation matrix, draw a correlated normal vector ``z`` via its
Cholesky factor, map to uniforms with the standard-normal CDF (the Gaussian copula), and push those
uniforms through each salience's triangular inverse-CDF — so the *marginals* are exactly the
triangular ranges the independent sampler uses, only now correlated. Fully seeded (rule 2):
same game + seed + structure = identical draws.

This never changes an existing run: it activates only when the caller opts in (``correlated=True`` /
``--correlated-sampling``); the record stores ``sampling="correlated"`` so the choice is disclosed.
"""

from __future__ import annotations

import math

import numpy as np

from schelling.mc.sampling import triangular_ppf
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.votes import weighted_median

# The committed within-coalition salience correlation — a fixed modelling constant, not fitted.
SALIENCE_RHO = 0.5


def _coalition_sides(game: GameSpec) -> np.ndarray:
    """Boolean coalition label per actor: True at/above the weighted median, False below it."""
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    weights = np.array([a.capability.mode * a.salience.mode for a in game.actors], dtype=np.float64)
    med = weighted_median(positions, weights) if weights.sum() > 0 else float(np.median(positions))
    return positions >= med


def salience_cholesky(game: GameSpec, rho: float = SALIENCE_RHO) -> np.ndarray:
    """Cholesky factor of the salience correlation matrix (equicorrelation ``rho`` within a bloc).

    Precomputed once per game; a per-draw sample is ``L @ standard_normal``. The block matrix is
    positive semi-definite for ``rho`` in [0, 1); a tiny jitter guards the Cholesky.
    """
    side = _coalition_sides(game)
    n = side.size
    corr = np.eye(n, dtype=np.float64)
    same = side[:, None] == side[None, :]
    corr[same] = rho
    np.fill_diagonal(corr, 1.0)
    return np.linalg.cholesky(corr + 1e-12 * np.eye(n))


def _normal_cdf(z: np.ndarray) -> np.ndarray:
    """Standard-normal CDF (the Gaussian copula link); ``math.erf`` elementwise (n is small)."""
    return np.array(
        [0.5 * (1.0 + math.erf(float(v) / math.sqrt(2.0))) for v in z], dtype=np.float64
    )


def sample_game_correlated(game: GameSpec, rng: np.random.Generator, chol: np.ndarray) -> GameSpec:
    """Draw one point-estimate game with salience correlated within coalitions (D41.4).

    ``chol`` is :func:`salience_cholesky` for this game. Positions and capabilities keep independent
    triangular draws; saliences share the coalition correlation through the Gaussian copula.
    """
    n = len(game.actors)
    u_sal = _normal_cdf(chol @ rng.standard_normal(n))
    u_pos = rng.random(n)
    u_cap = rng.random(n)
    actors = [
        Actor(
            id=a.id,
            name=a.name,
            position=TriangularEstimate.point(triangular_ppf(a.position, float(u_pos[i]))),
            salience=TriangularEstimate.point(triangular_ppf(a.salience, float(u_sal[i]))),
            capability=TriangularEstimate.point(triangular_ppf(a.capability, float(u_cap[i]))),
            evidence=list(a.evidence),
        )
        for i, a in enumerate(game.actors)
    ]
    return game.model_copy(update={"actors": actors})
