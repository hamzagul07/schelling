"""Effective weights, pairwise (Condorcet) contests, and the baseline forecasts.

BUILD_PLAN §4 steps 1-3, grounded in Scholz, Calbert & Smith (2011),
*Unravelling Bueno De Mesquita's Group Decision Model*, §3.2.

Equations (paper numbering; see DECISIONS.md for the interpretive mapping):

* Effective weight (BUILD_PLAN §4.1):  ``w_i = capability_i * salience_i / 100``.
* Votes actor *i* casts comparing positions ``x_j`` and ``x_k`` (Scholz eq. 26, expanded
  via eq. 14 to eq. 28):  ``v_i^{jk} = 2 c_i s_i (|x_i - x_k| - |x_i - x_j|) / R``, where
  ``R = x_max - x_min`` is the continuum range. Summed over actors (eq. 29) this is a
  Condorcet vote count: a positive total means ``x_j`` is preferred to ``x_k``.
* Baseline forecasts (BUILD_PLAN §4.3): the capability-weighted mean, and the weighted
  **median** — the Condorcet winner among the actors' positions, which Black's median-voter
  theorem guarantees exists for these single-peaked, distance-based preferences. The median
  is the model's headline forecast.

We follow BUILD_PLAN §4.2's stated form ``w_i * (|x_i - x_k| - |x_i - x_j|) / R``, i.e. we
fold ``c_i s_i`` into ``w_i`` (with the Policon ``/100`` normalization) and drop the
constant factor 2 from eq. 28. Because contest *outcomes* depend only on the sign of the
summed votes — and every downstream use of vote magnitude (alliance probability, eq. 30-31)
is a ratio in which constant factors cancel — this is exact, not an approximation. Logged in
DECISIONS.md.

All functions are pure and operate on 1-D numpy float arrays indexed by actor.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from schelling.schemas.question import GameSpec

FloatArray = npt.NDArray[np.float64]


def effective_weights(capability: FloatArray, salience: FloatArray) -> FloatArray:
    """Effective weight of each actor: ``w_i = capability_i * salience_i / 100``.

    BUILD_PLAN §4 step 1. Inputs are on the 0-100 Policon scale, so the product is
    re-normalized by 100 to keep weights on that scale.
    """
    capability = np.asarray(capability, dtype=np.float64)
    salience = np.asarray(salience, dtype=np.float64)
    if capability.shape != salience.shape:
        raise ValueError(
            f"capability and salience must have the same shape, "
            f"got {capability.shape} and {salience.shape}"
        )
    return capability * salience / 100.0


def net_votes(
    positions: FloatArray,
    weights: FloatArray,
    x_j: float,
    x_k: float,
    continuum_range: float,
) -> float:
    """Net votes for outcome ``x_j`` against ``x_k``, summed over all actors.

    BUILD_PLAN §4 step 2 (Scholz eq. 26-29):
    ``sum_i w_i * (|x_i - x_k| - |x_i - x_j|) / R``.

    A positive result means ``x_j`` defeats ``x_k`` in the pairwise contest; negative means
    ``x_k`` wins; zero is a tie. Each actor's contribution is positive when it sits closer to
    ``x_j`` than to ``x_k`` — it casts its weight toward the nearer outcome.
    """
    positions = np.asarray(positions, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    _check_range(continuum_range)
    contribution = weights * (np.abs(positions - x_k) - np.abs(positions - x_j))
    return float(np.sum(contribution) / continuum_range)


def contest_matrix(
    candidates: FloatArray,
    positions: FloatArray,
    weights: FloatArray,
    continuum_range: float,
) -> FloatArray:
    """Pairwise contest matrix ``M`` over candidate outcomes.

    ``M[a, b]`` is the net vote for ``candidates[a]`` against ``candidates[b]`` (BUILD_PLAN
    §4 step 2). ``M[a, b] > 0`` means candidate ``a`` defeats candidate ``b``; the matrix is
    antisymmetric (``M[a, b] == -M[b, a]``) and its diagonal is zero. A row that is
    non-negative everywhere identifies a Condorcet winner.
    """
    candidates = np.asarray(candidates, dtype=np.float64)
    positions = np.asarray(positions, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    _check_range(continuum_range)

    # dist[i, a] = |position_i - candidate_a|
    dist = np.abs(positions[:, None] - candidates[None, :])
    # M[a, b] = sum_i w_i * (dist[i, b] - dist[i, a]) / R
    weighted = weights[:, None] * dist  # [i, a]
    col_sums = weighted.sum(axis=0)  # over actors -> [a]
    matrix = (col_sums[None, :] - col_sums[:, None]) / continuum_range
    return matrix.astype(np.float64)


def weighted_mean(positions: FloatArray, weights: FloatArray) -> float:
    """Capability-weighted mean position: ``sum_i w_i x_i / sum_i w_i``.

    BUILD_PLAN §4 step 3. Raises if total weight is zero (an ill-posed game).
    """
    positions = np.asarray(positions, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    total = float(np.sum(weights))
    if total == 0.0:
        raise ValueError("total weight is zero; weighted mean is undefined")
    return float(np.sum(weights * positions) / total)


def weighted_median(positions: FloatArray, weights: FloatArray) -> float:
    """Weighted-median forecast — the Condorcet winner among actor positions.

    BUILD_PLAN §4 step 3: "the position that defeats every alternative in pairwise
    contests." For single-peaked, distance-based preferences this is exactly the classic
    weighted median, so we compute it directly from cumulative weight (an O(n log n),
    tie-deterministic route to the same point the contest matrix would elect).

    Tie convention: when the cumulative weight reaches exactly half the total at a position,
    that (lower) position wins — the standard *lower* weighted median. This makes the result
    a deterministic function of the inputs, as required for auditability.
    """
    positions = np.asarray(positions, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    total = float(np.sum(weights))
    if total == 0.0:
        raise ValueError("total weight is zero; weighted median is undefined")

    order = np.argsort(positions, kind="stable")
    sorted_positions = positions[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    # First position at which cumulative weight reaches half the total.
    half = total / 2.0
    idx = int(np.searchsorted(cumulative, half, side="left"))
    idx = min(idx, sorted_positions.size - 1)
    return float(sorted_positions[idx])


def game_mode_arrays(game: GameSpec) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Extract ``(positions, saliences, capabilities)`` mode-value arrays from a GameSpec.

    The deterministic solver consumes the ``mode`` of each triangular estimate; Monte Carlo
    (§6) will draw the low/high tails. Actor order is preserved.
    """
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    saliences = np.array([a.salience.mode for a in game.actors], dtype=np.float64)
    capabilities = np.array([a.capability.mode for a in game.actors], dtype=np.float64)
    return positions, saliences, capabilities


def _check_range(continuum_range: float) -> None:
    if continuum_range <= 0.0:
        raise ValueError(f"continuum_range must be positive, got {continuum_range}")
