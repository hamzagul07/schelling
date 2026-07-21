"""Advise mode (Session 7): a one-sided lever search from one actor's viewpoint.

Given a game and an advising actor, sweep the actor's own moves (position across the continuum,
salience up to 100 and down to a floor) and, for every other actor, a feasible shift toward the
advisor's ideal. Every candidate is solved with the SAME derived seeds for comparability, so
differences are attributable to the move alone. Benefit (closer to the actor's ideal) and cost
(position conceded) are reported separately, never combined.

Deterministic: same inputs + seed -> byte-identical AdviseRecord (CLAUDE.md rule 2). This is
lever-finding, not a playbook — opponents are held to the model's fixed behaviour.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

import numpy as np

from schelling.mc.monte_carlo import engine_version, forecast, run_monte_carlo
from schelling.schemas.forecast import AdviseRecord, ForecastRecord, OwnMove, PersuasionTarget
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.config import SolverConfig

_EPS = 1e-9


def _grid(lo: float, hi: float, step: float) -> list[float]:
    """Evenly-spaced values from ``lo`` to ``hi`` (inclusive), step ``step``."""
    if hi <= lo:
        return [round(lo, 6)]
    n = math.floor((hi - lo) / step + _EPS)
    vals = [round(lo + i * step, 6) for i in range(n + 1)]
    if vals[-1] < hi - _EPS:
        vals.append(round(hi, 6))
    return vals


def _set_point(game: GameSpec, actor_index: int, field: str, value: float) -> GameSpec:
    """A copy of ``game`` with one actor-field pinned to a point ``value`` (solver reads mode)."""
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


def _median(game: GameSpec, cfg: SolverConfig, draws: int, seed: int) -> float:
    mc = run_monte_carlo(game, cfg, n_draws=draws, seed=seed)
    return float(np.median(mc.median_distribution))


def _candidate_median(
    game: GameSpec, cfg: SolverConfig, idx: int, field: str, value: float, draws: int, seed: int
) -> float:
    return _median(_set_point(game, idx, field, value), cfg, draws, seed)


def _inputs_hash(
    game: GameSpec, cfg: SolverConfig, advise_cfg: Mapping[str, object], actor: str
) -> str:
    payload = {
        "game": game.model_dump(mode="json"),
        "config": cfg.model_dump(mode="json"),
        "advise": advise_cfg,
        "actor": actor,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def advise(
    game: GameSpec,
    advising_actor: str,
    *,
    solver_config: SolverConfig | None = None,
    draws_per_candidate: int = 2000,
    target_draws: int = 10000,
    seed: int = 42,
    grid_step: float | None = None,
    salience_floor: float = 20.0,
    created_at: str | None = None,
) -> tuple[AdviseRecord, ForecastRecord]:
    """Run the advise search and return ``(AdviseRecord, baseline ForecastRecord)``.

    Raises ``ValueError`` if ``advising_actor`` is not an actor in the game.

    ``grid_step`` sets the position sweep resolution; when ``None`` (the default) it is adaptive —
    the realized continuum span / 20 — so a year-scale game and a 0-100 game both get ~20 points
    (D8.0a). Salience is always swept at a fixed step of 5 (it lives on the 0-100 scale).
    """
    cfg = solver_config or SolverConfig()
    index = {a.id: i for i, a in enumerate(game.actors)}
    if advising_actor not in index:
        known = ", ".join(index)
        raise ValueError(f"actor {advising_actor!r} is not in this game (actors: {known}).")
    advisor_idx = index[advising_actor]
    advisor = game.actors[advisor_idx]
    ideal = advisor.position.mode

    # Baseline: the game as-is. The target-draws record is the authoritative reference; a
    # draws-per-candidate baseline is the comparison point for the (lighter) sweep.
    baseline_record = forecast(game, cfg, n_draws=target_draws, seed=seed, write=False)
    baseline_median = baseline_record.ensemble.median
    baseline_lite = _median(game, cfg, draws_per_candidate, seed)

    def benefit(after: float, before: float = baseline_lite) -> float:
        return abs(before - ideal) - abs(after - ideal)

    own_moves: list[OwnMove] = []
    # Position sweep across the realized continuum (span of all actors' position ranges).
    pos_lo = min(a.position.low for a in game.actors)
    pos_hi = max(a.position.high for a in game.actors)
    # Adaptive default: ~20 points across the realized span; explicit --grid-step overrides (D8.0a).
    pos_step = grid_step if grid_step is not None else max(round((pos_hi - pos_lo) / 20.0, 6), _EPS)
    sal_step = grid_step if grid_step is not None else 5.0
    for v in _grid(pos_lo, pos_hi, pos_step):
        m = _candidate_median(game, cfg, advisor_idx, "position", v, draws_per_candidate, seed)
        own_moves.append(
            OwnMove(
                dimension="position",
                value=v,
                settlement_median=m,
                benefit=benefit(m),
                cost=abs(v - ideal),
                beyond_stated_range=not (advisor.position.low <= v <= advisor.position.high),
            )
        )
    # Salience sweep: down to the floor and up to 100 (salience is on a 0-100 scale).
    for v in _grid(salience_floor, 100.0, sal_step):
        m = _candidate_median(game, cfg, advisor_idx, "salience", v, draws_per_candidate, seed)
        own_moves.append(
            OwnMove(
                dimension="salience",
                value=v,
                settlement_median=m,
                benefit=benefit(m),
                cost=0.0,
                beyond_stated_range=not (advisor.salience.low <= v <= advisor.salience.high),
            )
        )

    # Top 3 own moves by benefit (cost as tie-break); re-solved at target_draws for final numbers.
    ranked = sorted(own_moves, key=lambda mv: (-mv.benefit, mv.cost, mv.dimension, mv.value))
    top_moves: list[OwnMove] = []
    for mv in ranked[:3]:
        m = _candidate_median(game, cfg, advisor_idx, mv.dimension, mv.value, target_draws, seed)
        top_moves.append(
            OwnMove(
                dimension=mv.dimension,
                value=mv.value,
                settlement_median=m,
                benefit=benefit(m, baseline_median),
                cost=mv.cost,
                beyond_stated_range=mv.beyond_stated_range,
            )
        )
    top_moves.sort(key=lambda mv: (-mv.benefit, mv.cost, mv.dimension, mv.value))

    # Persuasion targets: feasible shifts of every OTHER actor toward the advisor's ideal.
    targets: list[PersuasionTarget] = []
    for j, a in enumerate(game.actors):
        if a.id == advising_actor:
            continue
        to_pos = a.position.high if ideal >= a.position.mode else a.position.low
        m_pos = _candidate_median(game, cfg, j, "position", to_pos, draws_per_candidate, seed)
        targets.append(
            PersuasionTarget(
                actor_id=a.id,
                dimension="position",
                from_value=a.position.mode,
                to_value=to_pos,
                settlement_median=m_pos,
                benefit=benefit(m_pos),
                kind="energize",  # pulling a position toward the advisor's ideal (D8.0b)
            )
        )
        # Salience: the feasible edge (within the actor's range) that most helps the advisor.
        best: PersuasionTarget | None = None
        for to_sal in (a.salience.low, a.salience.high):
            m_sal = _candidate_median(game, cfg, j, "salience", to_sal, draws_per_candidate, seed)
            cand = PersuasionTarget(
                actor_id=a.id,
                dimension="salience",
                from_value=a.salience.mode,
                to_value=to_sal,
                settlement_median=m_sal,
                benefit=benefit(m_sal),
                # raising an actor's salience energizes them; lowering it defuses them (D8.0b)
                kind="energize" if to_sal >= a.salience.mode else "defuse",
            )
            if best is None or cand.benefit > best.benefit:
                best = cand
        if best is not None:
            targets.append(best)
    targets.sort(key=lambda t: (-t.benefit, t.actor_id, t.dimension))

    advise_cfg: dict[str, str | float | int | bool] = {
        "draws_per_candidate": draws_per_candidate,
        "target_draws": target_draws,
        "grid_step": pos_step,  # effective position step (adaptive unless overridden)
        "salience_step": sal_step,
        "salience_floor": salience_floor,
    }
    hashed = _inputs_hash(game, cfg, advise_cfg, advising_actor)
    run_id = f"{game.question_id}-advise-{advising_actor}-s{seed}-{hashed[:12]}"
    record = AdviseRecord(
        question_id=game.question_id,
        run_id=run_id,
        engine_version=engine_version(),
        inputs_hash=hashed,
        seed=seed,
        created_at=created_at,
        advising_actor=advising_actor,
        ideal=ideal,
        baseline_median=baseline_median,
        baseline_run_id=baseline_record.run_id,
        advise_config=advise_cfg,
        solver_config=cfg.model_dump(mode="json"),
        own_moves=own_moves,
        top_moves=top_moves,
        persuasion_targets=targets,
        game=game,
    )
    return record, baseline_record
