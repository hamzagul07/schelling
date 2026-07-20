"""Triangular sampling: one draw materializes a fully point-estimate GameSpec (BUILD_PLAN §6).

Each ``(low, mode, high)`` TriangularEstimate is drawn from a triangular distribution. A point
estimate (``low == mode == high``) passes through unchanged with zero variance, so the
replication fixture is a valid Monte Carlo input.
"""

from __future__ import annotations

import numpy as np

from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate


def derive_rng(master_seed: int, draw_index: int) -> np.random.Generator:
    """A deterministic per-draw RNG derived from ``master_seed`` and ``draw_index``.

    Uses ``SeedSequence`` so distinct draws get independent, well-separated streams while the
    whole ensemble is reproducible from the master seed alone (CLAUDE.md rule 2).
    """
    seed_seq = np.random.SeedSequence(entropy=master_seed, spawn_key=(draw_index,))
    return np.random.default_rng(seed_seq)


def sample_triangular(estimate: TriangularEstimate, rng: np.random.Generator) -> float:
    """Draw one value from a triangular ``(low, mode, high)``.

    Degenerate point estimates (``low == high``) return the mode unchanged — numpy's
    ``triangular`` requires ``left < right``, and a point has zero variance anyway.
    """
    if estimate.low == estimate.high:
        return estimate.mode
    return float(rng.triangular(estimate.low, estimate.mode, estimate.high))


def sample_game(game: GameSpec, rng: np.random.Generator) -> GameSpec:
    """Materialize one point-estimate ``GameSpec`` by drawing every actor field.

    Actor order and all non-sampled fields (ids, continuum, template, evidence) are preserved,
    so the draw is a valid solver input and hashes stably.
    """
    sampled_actors = [
        Actor(
            id=actor.id,
            name=actor.name,
            position=TriangularEstimate.point(sample_triangular(actor.position, rng)),
            salience=TriangularEstimate.point(sample_triangular(actor.salience, rng)),
            capability=TriangularEstimate.point(sample_triangular(actor.capability, rng)),
            evidence=list(actor.evidence),
        )
        for actor in game.actors
    ]
    return game.model_copy(update={"actors": sampled_actors})
