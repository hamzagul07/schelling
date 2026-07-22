"""Move vocabulary v1 (Advise 2.0, Session 21): named diplomatic actions -> typed parameter deltas.

Loads ``moves.yaml`` and resolves each vocabulary move to a concrete ``(actor_index, field, value)``
candidate given the game and the advising actor, plus a :class:`MoveAction` describing the delta for
the report. Purely mechanical on positions/salience — flag-based moves through MT-1.0 mechanics are
deferred until after the model's reading (see the YAML).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Any, cast

import yaml

from schelling.schemas.forecast import MoveAction
from schelling.schemas.question import GameSpec


@dataclass(frozen=True)
class VocabMove:
    name: str
    dimension: str  # "position" | "salience"
    scope: str  # "self" | "target"
    sense: str  # toward_settlement | toward_advisor | increase | decrease
    magnitude: float
    rationale: str


def load_vocabulary() -> list[VocabMove]:
    """Load the move vocabulary from packaged ``moves.yaml`` (sorted by name for determinism)."""
    text = (files("schelling.advise") / "moves.yaml").read_text()
    raw = cast("list[dict[str, Any]]", yaml.safe_load(text)["moves"])
    moves = [
        VocabMove(
            name=str(m["name"]),
            dimension=str(m["dimension"]),
            scope=str(m["scope"]),
            sense=str(m["sense"]),
            magnitude=float(m["magnitude"]),
            rationale=str(m["rationale"]),
        )
        for m in raw
    ]
    return sorted(moves, key=lambda v: v.name)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _resolve_value(vm: VocabMove, mode: float, lo: float, hi: float, toward: float) -> float:
    """Resolve a vocab move's new value for one field from its current mode and stated range."""
    if vm.sense == "increase":
        return _clamp(mode + vm.magnitude, lo, hi)
    if vm.sense == "decrease":
        return _clamp(mode - vm.magnitude, lo, hi)
    # toward_settlement / toward_advisor: step `magnitude` toward the `toward` target
    direction = 1.0 if toward >= mode else -1.0
    return _clamp(mode + direction * vm.magnitude, lo, hi)


def resolve_self_move(
    vm: VocabMove, game: GameSpec, advisor_idx: int, settlement: float
) -> tuple[str, float, MoveAction] | None:
    """A self vocab move -> ``(field, new_value, action)`` for the advisor; None if not self."""
    if vm.scope != "self":
        return None
    a = game.actors[advisor_idx]
    est = a.position if vm.dimension == "position" else a.salience
    toward = settlement if vm.dimension == "position" else est.mode
    new = _resolve_value(vm, est.mode, est.low, est.high, toward)
    action = MoveAction(name=vm.name, rationale=vm.rationale, delta=_delta_str(vm, est.mode, new))
    return vm.dimension, new, action


def resolve_target_move(
    vm: VocabMove, game: GameSpec, target_idx: int, advisor_ideal: float
) -> tuple[str, float, MoveAction] | None:
    """A target vocab move -> ``(field, new_value, action)`` for ``target_idx``; None if self."""
    if vm.scope != "target":
        return None
    a = game.actors[target_idx]
    est = a.position if vm.dimension == "position" else a.salience
    toward = advisor_ideal if vm.dimension == "position" else est.mode
    new = _resolve_value(vm, est.mode, est.low, est.high, toward)
    action = MoveAction(
        name=f"{vm.name}({a.id})", rationale=vm.rationale, delta=_delta_str(vm, est.mode, new)
    )
    return vm.dimension, new, action


def _delta_str(vm: VocabMove, mode: float, new: float) -> str:
    return f"{vm.dimension} {mode:g} -> {new:g} ({vm.sense})"
