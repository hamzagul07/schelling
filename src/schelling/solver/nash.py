"""Nash and Kalai-Smorodinsky bargaining solutions over actor utilities (Session 41, D41.2).

Two cooperative-bargaining settlement models, as alternatives to the non-cooperative challenge model
and the compromise mean. Each actor ``i`` has ideal position ``p_i`` and bargaining weight
``w_i = capability_i * salience_i``; its utility for an outcome ``x`` is the linear loss
``u_i(x) = -|x - p_i|``. The **disagreement point** ``d`` (the no-deal outcome) is the
configured ``reference_point`` when present, else the weighted-median status quo. Each gain
over disagreement is ``g_i(x) = |d - p_i| - |x - p_i|`` (positive only where ``x`` is closer
to ``p_i`` than ``d`` is).

* **Nash** (:func:`nash_forecast`): the weighted Nash bargaining solution maximizes
  ``sum_i w_i * ln g_i(x)`` over the region where every gain is positive — the asymmetric Nash.
  On the 1-D continuum with linear utilities the objective is concave there, so the maximizer is
  unique; we find it by a deterministic fine grid search.
* **Kalai-Smorodinsky** (:func:`ks_forecast`): maximize the minimum *normalized* gain
  ``g_i(x) / G_i``, where ``G_i = |d - p_i|`` is actor ``i``'s max attainable gain (at ``x = p_i``)
  — equal fractions of each actor's ideal improvement (Kalai & Smorodinsky 1975).

Both fall back to the disagreement point when no outcome Pareto-improves on it, and both are pure,
deterministic, and LLM-free. Neither touches any existing solver's numerical path.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.votes import weighted_median

FloatArray = npt.NDArray[np.float64]

_GRID = 1001  # grid resolution for the 1-D line search (deterministic)


def _actors(game: GameSpec) -> tuple[FloatArray, FloatArray]:
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    weights = np.array([a.capability.mode * a.salience.mode for a in game.actors], dtype=np.float64)
    return positions, weights


def _disagreement(
    game: GameSpec, positions: FloatArray, weights: FloatArray, cfg: SolverConfig
) -> float:
    """The disagreement ``d``: the configured reference point, else the status-quo median."""
    if cfg.reference_point is not None:
        return float(cfg.reference_point)
    if weights.sum() == 0.0:
        return float(np.median(positions))
    return weighted_median(positions, weights)


def _grid(positions: FloatArray, d: float) -> FloatArray:
    lo = float(min(positions.min(), d))
    hi = float(max(positions.max(), d))
    if hi <= lo:
        return np.array([lo], dtype=np.float64)
    return np.linspace(lo, hi, _GRID)


def nash_forecast(game: GameSpec, config: SolverConfig | None = None) -> float:
    """The weighted Nash bargaining settlement on the 1-D continuum (D41.2)."""
    cfg = config or SolverConfig()
    positions, weights = _actors(game)
    if positions.size == 1:
        return float(positions[0])
    d = _disagreement(game, positions, weights, cfg)
    w = weights if weights.sum() > 0 else np.ones_like(weights)
    xs = _grid(positions, d)
    gains = np.abs(d - positions)[None, :] - np.abs(
        xs[:, None] - positions[None, :]
    )  # (grid, actor)
    feasible = np.all(gains > 0.0, axis=1)
    if not feasible.any():
        return d  # disagreement is already Pareto-optimal; no deal improves on it
    obj = np.full(xs.shape, -np.inf)
    g = gains[feasible]
    obj[feasible] = (w[None, :] * np.log(g)).sum(axis=1)
    return float(xs[int(np.argmax(obj))])


def ks_forecast(game: GameSpec, config: SolverConfig | None = None) -> float:
    """The Kalai-Smorodinsky settlement: maximize the minimum normalized gain (D41.2)."""
    cfg = config or SolverConfig()
    positions, weights = _actors(game)
    if positions.size == 1:
        return float(positions[0])
    d = _disagreement(game, positions, weights, cfg)
    g_max = np.abs(d - positions)  # each actor's max attainable gain (at x = p_i)
    active = g_max > 0.0  # actors with g_max == 0 are indifferent (ideal == disagreement)
    if not active.any():
        return d
    xs = _grid(positions, d)
    gains = np.abs(d - positions)[None, :] - np.abs(
        xs[:, None] - positions[None, :]
    )  # (grid, actor)
    norm = gains[:, active] / g_max[None, active]  # normalized gain per active actor
    min_norm = norm.min(axis=1)  # the binding (worst-off) active actor at each x
    if not (min_norm > 0.0).any():
        return d
    return float(xs[int(np.argmax(min_norm))])
