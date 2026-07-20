"""Deterministic solver core (BUILD_PLAN §4).

Pure functions only: no I/O, no globals, no network, no clocks. Same inputs → identical
outputs. Session 1 implements the vote layer (``votes``, steps 1-3).
"""

from schelling.solver.votes import (
    contest_matrix,
    effective_weights,
    game_mode_arrays,
    net_votes,
    weighted_mean,
    weighted_median,
)

__all__ = [
    "contest_matrix",
    "effective_weights",
    "game_mode_arrays",
    "net_votes",
    "weighted_mean",
    "weighted_median",
]
