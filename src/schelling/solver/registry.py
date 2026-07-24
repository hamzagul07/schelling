"""The solver-engine registry (Session 39, D39).

Every :class:`ForecastRecord` carries an integer ``engine_version``. ``schelling verify`` re-solves
a record through the numerical path it was **sealed under** — ``resolve(record.engine_version)`` —
not the current default, so a change to the engine can never silently alter a record sealed under an
earlier version. Version 1 is the Session-1..38 behaviour.

**How to change the engine without breaking a sealed forecast (the freeze rule).** Do NOT edit the
numerical path a released version points to. To change numerics: copy the affected code into a v2
variant, register it here under a new integer, and bump :data:`CURRENT_ENGINE_VERSION`. The
permanent regression gate (``test_all_sealed_records_verify_under_their_engine``) re-solves every
sealed record through its own version and fails if any median moves — so v1 stays frozen.
"""

from __future__ import annotations

from collections.abc import Callable

from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig

# A version's solve entrypoint: (game, config, *, n_draws, seed, model) -> a fresh ForecastRecord.
SolveFn = Callable[..., ForecastRecord]

CURRENT_ENGINE_VERSION = 1


def _solve_v1(
    game: GameSpec,
    config: SolverConfig,
    *,
    n_draws: int,
    seed: int,
    model: str,
) -> ForecastRecord:
    """Engine v1 — the Session-1..38 Monte-Carlo path. FROZEN: never edit this; to change numerics,
    register a new version and bump ``CURRENT_ENGINE_VERSION`` (see module docstring)."""
    from schelling.mc.monte_carlo import forecast

    return forecast(game, config, n_draws=n_draws, seed=seed, write=False, model=model)


# version -> solve entrypoint. Append new versions; never mutate a released one.
ENGINE_REGISTRY: dict[int, SolveFn] = {1: _solve_v1}


def resolve(version: int) -> SolveFn | None:
    """The solve entrypoint for an engine ``version``, or None if this build no longer ships it —
    in which case ``verify`` reports PASS-with-note rather than re-deriving it (D39.3)."""
    return ENGINE_REGISTRY.get(version)
