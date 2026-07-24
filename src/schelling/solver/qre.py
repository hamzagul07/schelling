"""Quantal-response variant of the challenge model (Session 41, D41.1).

The challenge model resolves each round by having every mover accept the single most-enforceable
offer made to it — a hard ``argmax`` over expected utility. That hard selection is where the
**degenerate median lock** (D12.3) comes from: the same offer wins every round, so the weighted
median never moves and the Monte-Carlo spread collapses.

Quantal response (McKelvey-Palfrey logit choice) softens exactly that step. A mover accepts offer
``m`` with probability proportional to ``exp(lambda * enforceability_m)`` — better offers win more
often, error scales to the enforceability gaps, and the rationality parameter **lambda is fixed
advance (1.0, disclosed in docs/PHASE-C-GATE.md), never fitted**. We take the *expected* accepted
position under those logit probabilities (a deterministic, seed-free "mean-field" realization), so
the solver stays auditable while its choices are soft. As lambda -> inf this recovers the exact
challenge model; a finite lambda lets the median move.

Everything else — the two-pass risk-adjusted EU matrix, the octant classification, the convergence
rule — is the challenge model's, imported unchanged. **This does not touch the challenge model's
numerical path** (`solver.model.run`); it is a separate entrypoint registered as its own `--solver`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from schelling.schemas.forecast import StoppingRule
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.convergence import has_converged
from schelling.solver.octants import Offer, classify
from schelling.solver.rounds import _round_eu, continuum_range
from schelling.solver.votes import weighted_mean, weighted_median

FloatArray = npt.NDArray[np.float64]

# The logit rationality parameter, FIXED A PRIORI (docs/PHASE-C-GATE.md) — never fitted to data.
QRE_LAMBDA = 1.0


@dataclass(frozen=True)
class QREResult:
    """The QRE solver's per-solve outputs (the fields the MC layer needs, plus the trajectory)."""

    forecast_median: float
    forecast_mean: float
    rounds_executed: int
    stopping_rule: StoppingRule
    median_trajectory: list[float]


def _expected_moves(offers: list[Offer], positions: FloatArray, lam: float) -> dict[int, float]:
    """Each mover's logit-expected new position over the offers made to it (D41.1).

    Two quantal-response softenings replace ``rounds._select_offer``'s hard "accept the single most
    enforceable offer, fully":

    * **Soft choice among offers** — the mover weights competing offers ``m`` (enforceability
      ``e_m``, target ``t_m``) by ``softmax(lambda e)``: an expected target ``T = sum p_m t_m``
      (better options chosen more often; error scales to the enforceability gaps).
    * **Soft acceptance** — the move is the logit choice between accepting and staying:
      ``phi = sigma(lambda * e_max)``, so the mover moves to ``c + phi (T - c)``.

    As ``lambda -> inf`` both collapse to the hard model (best offer, full move); finite ``lambda``
    soft. Movers with no offer stay put.
    """
    by_mover: dict[int, list[tuple[float, float]]] = {}
    for offer in offers:
        if offer.mover is None or offer.new_position is None:
            continue
        by_mover.setdefault(offer.mover, []).append((offer.enforceability, offer.new_position))
    moves: dict[int, float] = {}
    for mover, cands in by_mover.items():
        enf = np.array([e for e, _ in cands], dtype=np.float64)
        targets = np.array([t for _, t in cands], dtype=np.float64)
        w = np.exp(lam * (enf - enf.max()))  # shift for numerical stability; monotone in enf
        expected_target = float((w / w.sum()) @ targets)
        phi = 1.0 / (1.0 + np.exp(-lam * float(enf.max())))  # logit accept-vs-stay probability
        current = float(positions[mover])
        moves[mover] = current + phi * (expected_target - current)
    return moves


def run_qre(
    game: GameSpec, config: SolverConfig | None = None, *, lam: float = QRE_LAMBDA
) -> QREResult:
    """Solve ``game`` with the quantal-response challenge model (see module docstring)."""
    cfg = config or SolverConfig()
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    saliences = np.array([a.salience.mode for a in game.actors], dtype=np.float64)
    capabilities = np.array([a.capability.mode for a in game.actors], dtype=np.float64)
    cs_weights = capabilities * saliences

    median_trajectory: list[float] = []
    stopping_rule = StoppingRule.ROUND_CAP
    mean_end = weighted_mean(positions, cs_weights)
    n = positions.size

    for _ in range(cfg.max_rounds):
        mu = weighted_median(positions, cs_weights)
        cont_range = continuum_range(positions, cfg)
        if cont_range <= 0.0:  # degenerate range: nothing can move (as in rounds.run_round)
            median_trajectory.append(mu)
            stopping_rule = StoppingRule.CONVERGED
            break
        eu, _r = _round_eu(positions, saliences, cs_weights, mu, cont_range, cfg)
        offers: list[Offer] = []
        for i in range(n):
            for j in range(i + 1, n):
                offers.append(
                    classify(
                        a=float(eu[i, j]),
                        b=float(eu[j, i]),
                        i=i,
                        j=j,
                        x_i=float(positions[i]),
                        x_j=float(positions[j]),
                        conflict_resolves=cfg.conflict_resolves,
                    )
                )
        moves = _expected_moves(offers, positions, lam)
        new_positions = positions.copy()
        for mover, target in moves.items():
            new_positions[mover] = target
        positions = new_positions
        median_end = weighted_median(positions, cs_weights)
        mean_end = weighted_mean(positions, cs_weights)
        median_trajectory.append(median_end)
        if has_converged(median_trajectory, cfg.convergence_epsilon, cfg.convergence_patience):
            stopping_rule = StoppingRule.CONVERGED
            break

    return QREResult(
        forecast_median=median_trajectory[-1],
        forecast_mean=mean_end,
        rounds_executed=len(median_trajectory),
        stopping_rule=stopping_rule,
        median_trajectory=median_trajectory,
    )
