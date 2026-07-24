"""Sobol variance-based global sensitivity, a second panel beside the tornado (Session 40, D40.3).

The tornado moves one parameter at a time between its low and high and reads the swing in the
forecast; it says nothing about **interactions** or about how much of the *output variance* a
parameter drives across the whole input space. Sobol indices do exactly that:

* **First-order** ``S_i``: the share of output variance explained by parameter ``i`` alone.
* **Total-order** ``S_Ti``: the share explained by ``i`` including every interaction it takes part
  in. ``S_Ti >= S_i``; a large gap means ``i`` matters mostly *through* interactions.

Estimated with **Saltelli sampling** and the Saltelli (2010) first-order / Jansen (2010) total-order
estimators, over the **same triangular input ranges the Monte-Carlo layer samples** (each ranged
actor field mapped through its triangular inverse-CDF, so the sensitivity is measured against the
same distribution the forecast uses). Two base samples ``A`` and ``B`` plus the ``2k`` cross
matrices ``A_B^(i)`` and ``B_A^(i)`` cost **``N * (2k + 2)`` model solves**; both cross designs
symmetrize each estimator. Everything is **seeded** (CLAUDE.md rule 2): same game + N + seed =
identical indices.

References: Saltelli et al. (2010), *Variance based sensitivity analysis of model output*,
Comput. Phys. Commun. 181; Jansen (1999) for the total-order estimator.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from schelling.mc.monte_carlo import MODEL_CHALLENGE, MODEL_COMPROMISE, _compromise_forecast
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

_FIELDS = ("position", "salience", "capability")

Model = Callable[[np.ndarray], np.ndarray]  # (m, k) real inputs -> (m,) outputs
Transform = Callable[[np.ndarray], np.ndarray]  # (m, k) in [0,1] -> (m, k) real inputs


@dataclass(frozen=True)
class SobolResult:
    """First- and total-order Sobol indices per parameter, with the sampling cost recorded."""

    labels: list[str]
    first_order: list[float]  # S_i — share of variance from the parameter alone
    total_order: list[float]  # S_Ti — share including interactions (>= S_i)
    n: int  # base sample size
    k: int  # number of ranged parameters
    seed: int
    model: str  # "compromise" | "challenge"

    @property
    def cost(self) -> int:
        """Number of model solves spent: ``N * (2k + 2)``."""
        return self.n * (2 * self.k + 2)


def _triangular_ppf(u: np.ndarray, low: float, mode: float, high: float) -> np.ndarray:
    """Inverse-CDF of the triangular ``(low, mode, high)`` — the distribution the MC samples."""
    if high <= low:
        return np.full_like(u, low)
    c = (mode - low) / (high - low)
    out = np.empty_like(u)
    left = u < c
    out[left] = low + np.sqrt(u[left] * (high - low) * (mode - low))
    out[~left] = high - np.sqrt((1.0 - u[~left]) * (high - low) * (high - mode))
    return out


def sobol_indices(model: Model, transform: Transform, k: int, *, n: int, seed: int) -> SobolResult:
    """Generic Saltelli Sobol estimator; ``labels``/``model`` name are filled by the caller.

    ``transform`` maps a ``[0,1]^k`` sample to the model's real input space; ``model`` maps an
    ``(m, k)`` array of real inputs to ``(m,)`` outputs. Costs ``n * (2k + 2)`` calls to ``model``.
    """
    rng = np.random.default_rng(seed)
    a01 = rng.random((n, k))
    b01 = rng.random((n, k))
    f_a = np.asarray(model(transform(a01)), dtype=np.float64)
    f_b = np.asarray(model(transform(b01)), dtype=np.float64)
    var = float(np.var(np.concatenate([f_a, f_b])))
    first: list[float] = []
    total: list[float] = []
    if var <= 0.0:  # a degenerate (locked) output has no variance to apportion
        return SobolResult([""] * k, [0.0] * k, [0.0] * k, n, k, seed, "")
    for i in range(k):
        ab01 = a01.copy()
        ab01[:, i] = b01[:, i]
        ba01 = b01.copy()
        ba01[:, i] = a01[:, i]
        f_ab = np.asarray(model(transform(ab01)), dtype=np.float64)
        f_ba = np.asarray(model(transform(ba01)), dtype=np.float64)
        # First order (Saltelli 2010): S_i = mean(f_B (f_AB - f_A)) / Var; symmetrized with B_A.
        s_ab = float(np.mean(f_b * (f_ab - f_a))) / var
        s_ba = float(np.mean(f_a * (f_ba - f_b))) / var
        # Total order (Jansen): S_Ti = mean((f_A - f_AB)^2) / (2 Var); symmetrized with B_A.
        st_ab = float(np.mean((f_a - f_ab) ** 2)) / (2.0 * var)
        st_ba = float(np.mean((f_b - f_ba) ** 2)) / (2.0 * var)
        first.append((s_ab + s_ba) / 2.0)
        total.append((st_ab + st_ba) / 2.0)
    return SobolResult([""] * k, first, total, n, k, seed, "")


def _ranged_params(game: GameSpec) -> list[tuple[int, str]]:
    """The (actor_index, field) pairs with a real range — the same set the tornado varies."""
    out: list[tuple[int, str]] = []
    for ai, actor in enumerate(game.actors):
        for field in _FIELDS:
            est: TriangularEstimate = getattr(actor, field)
            if est.low < est.high:
                out.append((ai, field))
    return out


def sobol_for_game(
    game: GameSpec,
    config: SolverConfig | None = None,
    *,
    model: str = MODEL_COMPROMISE,
    n: int = 512,
    seed: int = 0,
) -> SobolResult:
    """Sobol indices for a game's ranged actor fields under the compromise or challenge solver.

    The compromise solver (a closed-form weighted mean) is cheap, so it is the default and runs at
    the full ``N * (2k + 2)`` cost quickly; the challenge (BDM) solver re-simulates every solve and
    is far slower — the CLI gates it behind a flag and reports the cost. Same game + N + seed =
    identical indices (CLAUDE.md rule 2).
    """
    cfg = config or SolverConfig()
    params = _ranged_params(game)
    k = len(params)
    labels = [f"{game.actors[ai].id}.{field}" for ai, field in params]
    if k == 0:  # no ranged parameter — nothing to apportion
        return SobolResult([], [], [], n, 0, seed, model)
    specs = [
        (
            getattr(game.actors[ai], field).low,
            getattr(game.actors[ai], field).mode,
            getattr(game.actors[ai], field).high,
        )
        for ai, field in params
    ]

    def transform(u01: np.ndarray) -> np.ndarray:
        cols = [_triangular_ppf(u01[:, i], *specs[i]) for i in range(k)]
        return np.column_stack(cols)

    def _point_game(row: np.ndarray) -> GameSpec:
        actors = list(game.actors)
        for i, (ai, field) in enumerate(params):
            a = actors[ai]
            actors[ai] = Actor(
                id=a.id,
                name=a.name,
                position=a.position,
                salience=a.salience,
                capability=a.capability,
                evidence=list(a.evidence),
            ).model_copy(update={field: TriangularEstimate.point(float(row[i]))})
        return game.model_copy(update={"actors": actors})

    def model_fn(inputs: np.ndarray) -> np.ndarray:
        out = np.empty(inputs.shape[0], dtype=np.float64)
        for r in range(inputs.shape[0]):
            g = _point_game(inputs[r])
            if model == MODEL_CHALLENGE:
                out[r] = run(g, cfg).forecast_median
            else:
                out[r] = _compromise_forecast(g)
        return out

    result = sobol_indices(model_fn, transform, k, n=n, seed=seed)
    return SobolResult(labels, result.first_order, result.total_order, n, k, seed, model)


def format_sobol(result: SobolResult) -> str:
    """Render the Sobol panel as plain text, labelled against the tornado's meaning (D40.3)."""
    if result.k == 0:
        return "Sobol: no ranged parameters — every input is a point estimate (no variance)."
    order = sorted(range(result.k), key=lambda i: -result.total_order[i])
    width = max(len(lab) for lab in result.labels)
    lines = [
        f"Sobol global sensitivity — {result.model} solver, N={result.n}, "
        f"cost {result.cost} solves, seed {result.seed}",
        "Share of output variance (Sobol) — distinct from the tornado's single-parameter swings.",
        f"  {'parameter':<{width}}  {'first-order':>12}  {'total-order':>12}",
    ]
    for i in order:
        lines.append(
            f"  {result.labels[i]:<{width}}  {result.first_order[i]:>12.4f}  "
            f"{result.total_order[i]:>12.4f}"
        )
    return "\n".join(lines)
