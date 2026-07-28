"""Three-way decomposition of total forecast variance (Session 45, D45.3).

A forecast drawn from an elicitation ensemble varies for three reasons, and this module apportions
the total variance among them so the shares **sum to exactly 1**:

* **elicitation** — which draft you believe (variance *across* the independent drafts);
* **input ranges** — the triangular uncertainty *within* a draft (the Monte-Carlo spread);
* **model choice** — which solver you run (variance *across* solvers).

Method. Treat the forecast as a function of a draft ``D`` (N values), an input sample ``X`` (S
Monte-Carlo draws), and a model ``M`` (K solvers), evaluated on the balanced ``N x K x S`` grid, and
apply the law of total variance nested in the order D, then M, then X:

    Var(f) = Var_D[E(f|D)]            # elicitation
           + E_D[Var_M(E(f|D,M))]     # model choice
           + E_D E_M[Var_X(f|D,M)]    # input ranges

These three non-negative terms sum *exactly* to the total (population) variance of the grid, so the
normalized shares sum to 1. The nesting order fixes how interaction variance is attributed; it is
stated with the result rather than hidden. The input-range term is the mean of the within-cell
Monte-Carlo variances — the very quantity ``mc.sobol`` apportions among parameters, reused here as
the input share (Sobol answers *which* inputs drive it; this answers *how much* of the total it is).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from schelling.schemas.elicitation import VarianceShares
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig

FloatArray = npt.NDArray[np.float64]


def variance_shares(forecasts: FloatArray, *, method: str = "") -> VarianceShares:
    """Decompose an ``(N_drafts, K_models, S_samples)`` grid of forecasts into three shares (D45.3).

    Uses population variances on a balanced grid, so the elicitation / model-choice / input-range
    terms sum to the grid's total variance exactly; the returned shares therefore sum to 1 (or all
    zero when the grid is constant). See the module docstring for the nested-variance identity.
    """
    f = np.asarray(forecasts, dtype=np.float64)
    if f.ndim != 3:
        raise ValueError(f"forecasts must be (N_drafts, K_models, S_samples), got shape {f.shape}")
    cell_mean = f.mean(axis=2)  # E(f | D, M)          -> (N, K)
    cell_var = f.var(axis=2)  # Var_X(f | D, M)        -> (N, K)
    draft_mean = cell_mean.mean(axis=1)  # E(f | D)    -> (N,)
    elicitation = float(draft_mean.var())  # Var_D[E(f|D)]
    model_choice = float(cell_mean.var(axis=1).mean())  # E_D[Var_M(E(f|D,M))]
    input_ranges = float(cell_var.mean())  # E_D E_M[Var_X(f|D,M)]
    total = elicitation + model_choice + input_ranges
    if total <= 0.0:  # a constant grid — no variance to apportion
        return VarianceShares(
            elicitation=0.0,
            input_ranges=0.0,
            model_choice=0.0,
            total_variance=0.0,
            method=method or _method(f.shape),
        )
    return VarianceShares(
        elicitation=elicitation / total,
        input_ranges=input_ranges / total,
        model_choice=model_choice / total,
        total_variance=total,
        method=method or _method(f.shape),
    )


def _method(shape: tuple[int, ...]) -> str:
    n, k, s = shape
    return (
        f"nested law-of-total-variance (drafts -> solvers -> input ranges) over an "
        f"{n} x {k} x {s} draft x solver x Monte-Carlo grid; shares sum to 1"
    )


def decompose_question(
    games: list[GameSpec],
    models: list[str],
    *,
    config: SolverConfig | None = None,
    n_draws: int = 2000,
    seed: int = 0,
) -> VarianceShares:
    """Build the forecast grid by solving every draft under every solver, then decompose (D45.3).

    Each ``(draft, solver)`` cell is a Monte-Carlo ensemble over that draft's input ranges (a shared
    ``seed`` keeps the input sampling comparable across cells). Reuses ``run_monte_carlo`` — the
    engine the Sobol layer builds on. ``games`` are the drafts' games in draft order.
    """
    from schelling.mc.monte_carlo import run_monte_carlo

    if not games:
        raise ValueError("decompose_question needs at least one draft")
    if not models:
        raise ValueError("decompose_question needs at least one solver model")
    cfg = config or SolverConfig()
    grid = np.empty((len(games), len(models), n_draws), dtype=np.float64)
    for i, game in enumerate(games):
        for j, model in enumerate(models):
            mc = run_monte_carlo(game, cfg, n_draws=n_draws, seed=seed, model=model)
            grid[i, j, :] = mc.median_distribution
    return variance_shares(grid)
