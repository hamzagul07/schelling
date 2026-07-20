"""Deterministic solver core (BUILD_PLAN §4).

Pure functions only: no I/O, no globals, no network, no clocks. Same inputs → identical
outputs.
"""

from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.model import run
from schelling.solver.votes import (
    contest_matrix,
    effective_weights,
    game_mode_arrays,
    net_votes,
    weighted_mean,
    weighted_median,
)

__all__ = [
    "RangeMode",
    "SolverConfig",
    "contest_matrix",
    "effective_weights",
    "game_mode_arrays",
    "net_votes",
    "run",
    "weighted_mean",
    "weighted_median",
]
