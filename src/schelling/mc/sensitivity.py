"""One-at-a-time tornado sensitivity (BUILD_PLAN §6).

Re-solve deterministically with each actor-field pinned to its ``low`` and then its ``high``,
all other fields at ``mode``; rank parameters by the resulting swing in the forecast median.
The output is the "what to watch" list.
"""

from __future__ import annotations

from schelling.schemas.forecast import SensitivityEntry
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

_FIELDS = ("position", "salience", "capability")


def _vary(game: GameSpec, actor_index: int, field: str, value: float) -> GameSpec:
    """Return a copy of ``game`` with one actor-field pinned to a point ``value``.

    The solver reads each estimate's ``mode``, so pinning ``field`` to ``point(value)`` sets
    that value while every other field keeps its original mode.
    """
    actor = game.actors[actor_index]
    updated = Actor(
        id=actor.id,
        name=actor.name,
        position=actor.position,
        salience=actor.salience,
        capability=actor.capability,
        evidence=list(actor.evidence),
    ).model_copy(update={field: TriangularEstimate.point(value)})
    actors = list(game.actors)
    actors[actor_index] = updated
    return game.model_copy(update={"actors": actors})


def tornado(game: GameSpec, config: SolverConfig | None = None) -> list[SensitivityEntry]:
    """Compute the tornado table, ranked by absolute forecast swing (descending).

    Only fields with a real range (``low < high``) are included — a point estimate has zero
    swing by construction and would only pad the list.
    """
    cfg = config or SolverConfig()
    entries: list[SensitivityEntry] = []
    for k, actor in enumerate(game.actors):
        for field in _FIELDS:
            est: TriangularEstimate = getattr(actor, field)
            if est.low == est.high:
                continue
            f_low = run(_vary(game, k, field, est.low), cfg).forecast_median
            f_high = run(_vary(game, k, field, est.high), cfg).forecast_median
            entries.append(
                SensitivityEntry(
                    parameter=f"{actor.id}.{field}",
                    actor_id=actor.id,
                    field=field,
                    low_value=est.low,
                    high_value=est.high,
                    forecast_at_low=f_low,
                    forecast_at_high=f_high,
                    swing=f_high - f_low,
                )
            )
    entries.sort(key=lambda e: (-abs(e.swing), e.parameter))
    return entries


def format_tornado(entries: list[SensitivityEntry]) -> str:
    """Render the tornado as a human-readable "what to watch" list."""
    if not entries:
        return "No ranged parameters — every input is a point estimate (zero sensitivity)."
    width = max(len(e.parameter) for e in entries)
    lines = ["What to watch (parameters ranked by forecast swing):"]
    for e in entries:
        lines.append(
            f"  {e.parameter:<{width}}  swing {e.swing:+6.2f}  "
            f"[{e.field} {e.low_value:g}->{e.forecast_at_low:.2f} .. "
            f"{e.high_value:g}->{e.forecast_at_high:.2f}]"
        )
    return "\n".join(lines)
