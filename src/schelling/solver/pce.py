"""Probabilistic Condorcet election — the KTAB settlement method (Session 41, D41.3).

KTAB (the open-source BDM successor, Wise/Bueno de Mesquita/Kugler) settles a one-dimensional issue
by a **probabilistic Condorcet election** over the actors' positions rather than by a single
deterministic Condorcet winner. Implementing the same method here makes KTAB's published forecasts
directly comparable to ours. The exact procedure used (disclosed, per CLAUDE.md rule 3) is:

1. **Candidates** are the distinct actor positions.
2. **Pairwise victory probability.** For candidates ``a`` and ``b``, each actor backs whichever it
   sits closer to, casting its weight ``w_i = capability_i * salience_i`` (an equidistant actor
   splits its weight). With support weights ``U_a`` and ``U_b``, the probability ``a`` beats ``b``
   is ``pv[a,b] = U_a / (U_a + U_b)`` (0.5 when both are zero) — a coalition-strength ratio, the
   BDM/KTAB "probability of victory" at victory-exponent 1.
3. **Selection probability.** KTAB's ``scalarPCE`` takes the stationary distribution of the victory
   matrix: iterate ``p ← normalize(PV * p)`` from a uniform start to a fixed point (the dominant
   eigenvector of the row-stochastic ``PV`` with ``pv[a,a] = 0.5``). The result is each candidate's
   probability of winning the election.
4. **Forecast** = the expected outcome ``sum_a p_a * candidate_a``; :func:`pce_distribution` also
   returns the modal candidate and the full probability vector.

Pure, deterministic (power iteration to a fixed tolerance), LLM-free. Touches no existing solver.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from schelling.schemas.question import GameSpec

FloatArray = npt.NDArray[np.float64]

_MAX_ITERS = 1000
_TOL = 1e-12


@dataclass(frozen=True)
class PCEResult:
    """The probabilistic Condorcet election outcome."""

    candidates: list[float]
    probabilities: list[float]  # aligned with candidates; sums to 1
    forecast: float  # expected outcome, sum p_a candidate_a
    modal: float  # the most probable candidate


def _victory_matrix(
    candidates: FloatArray, positions: FloatArray, weights: FloatArray
) -> FloatArray:
    """``PV[a,b]`` = probability candidate ``a`` beats ``b`` by coalition-support ratio (D41.3)."""
    n = candidates.size
    # dist[i, a] = |position_i - candidate_a|
    dist = np.abs(positions[:, None] - candidates[None, :])
    pv = np.full((n, n), 0.5, dtype=np.float64)
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            da, db = dist[:, a], dist[:, b]
            support_a = float(weights[da < db].sum()) + 0.5 * float(weights[da == db].sum())
            support_b = float(weights[db < da].sum()) + 0.5 * float(weights[da == db].sum())
            total = support_a + support_b
            pv[a, b] = support_a / total if total > 0.0 else 0.5
    return pv


def _stationary(pv: FloatArray) -> FloatArray:
    """Stationary probabilities: power-iterate ``p <- normalize(PV p)`` to a fixed point."""
    n = pv.shape[0]
    p = np.full(n, 1.0 / n, dtype=np.float64)
    for _ in range(_MAX_ITERS):
        nxt = pv @ p
        s = nxt.sum()
        if s <= 0.0:
            break
        nxt = nxt / s
        if float(np.abs(nxt - p).max()) < _TOL:
            p = nxt
            break
        p = nxt
    return p


def pce_distribution(game: GameSpec) -> PCEResult:
    """Full probabilistic Condorcet election over a game's actor positions (D41.3)."""
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    weights = np.array([a.capability.mode * a.salience.mode for a in game.actors], dtype=np.float64)
    candidates = np.unique(positions)  # sorted distinct positions
    if candidates.size == 1:
        c = float(candidates[0])
        return PCEResult([c], [1.0], c, c)
    if weights.sum() == 0.0:
        weights = np.ones_like(weights)
    pv = _victory_matrix(candidates, positions, weights)
    p = _stationary(pv)
    forecast = float(p @ candidates)
    modal = float(candidates[int(np.argmax(p))])
    return PCEResult(candidates.tolist(), p.tolist(), forecast, modal)


def pce_forecast(game: GameSpec, config: object | None = None) -> float:
    """The probabilistic Condorcet expected outcome (config accepted for a uniform solver API)."""
    return pce_distribution(game).forecast
