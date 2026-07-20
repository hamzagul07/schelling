"""Solver orchestration: ``run(game, config) -> SolverResult``.

BUILD_PLAN §4 (steps 3-8) and §1 (the solver is pure: no I/O, no globals, no network). Loops
rounds, applies the stopping rule, and emits a fully-populated per-round audit log.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from schelling.schemas.forecast import RoundLog, SolverResult, StoppingRule
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.convergence import has_converged
from schelling.solver.octants import Relation
from schelling.solver.rounds import run_round
from schelling.solver.votes import weighted_mean, weighted_median

FloatArray = npt.NDArray[np.float64]


def run(game: GameSpec, config: SolverConfig | None = None) -> SolverResult:
    """Solve ``game`` deterministically and return a :class:`SolverResult`.

    Consumes the ``mode`` of each triangular estimate (D1.4). Records the end-of-round
    weighted median (headline forecast) and mean for every round, plus the octant matrix and
    accepted offers, and which stopping rule fired.
    """
    cfg = config or SolverConfig()
    ids = [a.id for a in game.actors]
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    saliences = np.array([a.salience.mode for a in game.actors], dtype=np.float64)
    capabilities = np.array([a.capability.mode for a in game.actors], dtype=np.float64)
    cs_weights = capabilities * saliences  # c_i s_i (Scholz vote weight); scale-free downstream

    logs: list[RoundLog] = []
    median_trajectory: list[float] = []
    stopping_rule = StoppingRule.ROUND_CAP

    for round_index in range(cfg.max_rounds):
        outcome = run_round(positions, saliences, cs_weights, cfg)
        new_positions = outcome.new_positions
        median_end = weighted_median(new_positions, cs_weights)
        mean_end = weighted_mean(new_positions, cs_weights)

        logs.append(
            RoundLog(
                round_index=round_index,
                positions={ids[k]: float(new_positions[k]) for k in range(len(ids))},
                weighted_mean=mean_end,
                weighted_median=median_end,
                offers=[
                    {ids[mover]: float(target)}
                    for mover, target in sorted(outcome.accepted_offers.items())
                ],
                octant_matrix=_octant_matrix(outcome.relations, ids),
            )
        )
        median_trajectory.append(median_end)
        positions = new_positions

        if has_converged(median_trajectory, cfg.convergence_epsilon, cfg.convergence_patience):
            stopping_rule = StoppingRule.CONVERGED
            break

    return SolverResult(
        rounds=logs,
        rounds_executed=len(logs),
        stopping_rule=stopping_rule,
        forecast_median=median_trajectory[-1],
        forecast_mean=logs[-1].weighted_mean,
    )


def _octant_matrix(
    relations: dict[tuple[int, int], Relation], ids: list[str]
) -> dict[str, dict[str, str]]:
    """Build the ``{actor_id: {actor_id: relation}}`` matrix for the round log."""
    matrix: dict[str, dict[str, str]] = {}
    for (i, j), relation in relations.items():
        matrix.setdefault(ids[i], {})[ids[j]] = str(relation)
    return matrix
