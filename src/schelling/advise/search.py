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
from collections.abc import Callable, Mapping

import numpy as np

from schelling.mc.monte_carlo import engine_version, forecast, run_monte_carlo
from schelling.schemas.forecast import (
    AdviseLens,
    AdviseRecord,
    ForecastRecord,
    OwnMove,
    PersuasionTarget,
)
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.config import SolverConfig

_EPS = 1e-9
Settle = Callable[[GameSpec], float]


def _compromise_settlement(game: GameSpec) -> float:
    """The compromise model's exact settlement: the capability x salience weighted mean (D12.4).

    Closed-form — no simulation. A move's effect is exact: shifting actor i's position by d moves
    the settlement by ``(w_i / Σw)·d``; changing its salience re-weights the mean analytically.
    """
    w = [a.capability.mode * a.salience.mode for a in game.actors]
    x = [a.position.mode for a in game.actors]
    total = sum(w)
    if total <= 0:
        return sum(x) / len(x)
    return sum(wi * xi for wi, xi in zip(w, x, strict=True)) / total


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


def _lens_moves(
    game: GameSpec,
    advisor_idx: int,
    ideal: float,
    settle_lite: Settle,
    settle_final: Settle,
    baseline_lite: float,
    baseline_final: float,
    pos_step: float,
    sal_step: float,
    salience_floor: float,
) -> tuple[list[OwnMove], list[OwnMove], list[PersuasionTarget]]:
    """Sweep own moves + persuasion targets under a given settlement function (D12.4).

    ``settle_lite``/``settle_final`` map a modified game to a settlement (a Monte-Carlo median for
    the challenge lens; the exact weighted mean for the compromise lens). Benefit/cost logic is
    identical across lenses — only how the settlement is computed differs.
    """
    advisor = game.actors[advisor_idx]

    def benefit(after: float, before: float) -> float:
        return abs(before - ideal) - abs(after - ideal)

    own_moves: list[OwnMove] = []
    pos_lo = min(a.position.low for a in game.actors)
    pos_hi = max(a.position.high for a in game.actors)
    for v in _grid(pos_lo, pos_hi, pos_step):
        m = settle_lite(_set_point(game, advisor_idx, "position", v))
        own_moves.append(
            OwnMove(
                dimension="position",
                value=v,
                settlement_median=m,
                benefit=benefit(m, baseline_lite),
                cost=abs(v - ideal),
                beyond_stated_range=not (advisor.position.low <= v <= advisor.position.high),
            )
        )
    for v in _grid(salience_floor, 100.0, sal_step):
        m = settle_lite(_set_point(game, advisor_idx, "salience", v))
        own_moves.append(
            OwnMove(
                dimension="salience",
                value=v,
                settlement_median=m,
                benefit=benefit(m, baseline_lite),
                cost=0.0,
                beyond_stated_range=not (advisor.salience.low <= v <= advisor.salience.high),
            )
        )

    ranked = sorted(own_moves, key=lambda mv: (-mv.benefit, mv.cost, mv.dimension, mv.value))
    top_moves: list[OwnMove] = []
    for mv in ranked[:3]:
        m = settle_final(_set_point(game, advisor_idx, mv.dimension, mv.value))
        top_moves.append(
            OwnMove(
                dimension=mv.dimension,
                value=mv.value,
                settlement_median=m,
                benefit=benefit(m, baseline_final),
                cost=mv.cost,
                beyond_stated_range=mv.beyond_stated_range,
            )
        )
    top_moves.sort(key=lambda mv: (-mv.benefit, mv.cost, mv.dimension, mv.value))

    targets: list[PersuasionTarget] = []
    for j, a in enumerate(game.actors):
        if j == advisor_idx:
            continue
        to_pos = a.position.high if ideal >= a.position.mode else a.position.low
        m_pos = settle_lite(_set_point(game, j, "position", to_pos))
        targets.append(
            PersuasionTarget(
                actor_id=a.id,
                dimension="position",
                from_value=a.position.mode,
                to_value=to_pos,
                settlement_median=m_pos,
                benefit=benefit(m_pos, baseline_lite),
                kind="energize",
            )
        )
        best: PersuasionTarget | None = None
        for to_sal in (a.salience.low, a.salience.high):
            m_sal = settle_lite(_set_point(game, j, "salience", to_sal))
            cand = PersuasionTarget(
                actor_id=a.id,
                dimension="salience",
                from_value=a.salience.mode,
                to_value=to_sal,
                settlement_median=m_sal,
                benefit=benefit(m_sal, baseline_lite),
                kind="energize" if to_sal >= a.salience.mode else "defuse",
            )
            if best is None or cand.benefit > best.benefit:
                best = cand
        if best is not None:
            targets.append(best)
    targets.sort(key=lambda t: (-t.benefit, t.actor_id, t.dimension))
    return own_moves, top_moves, targets


def advise(
    game: GameSpec,
    advising_actor: str,
    *,
    model: str = "challenge",
    solver_config: SolverConfig | None = None,
    draws_per_candidate: int = 2000,
    target_draws: int = 10000,
    seed: int = 42,
    grid_step: float | None = None,
    salience_floor: float = 20.0,
    created_at: str | None = None,
    strategy: bool = False,
    mode: str = "levers",
    robustness_draws: int = 400,
    response_draws: int = 500,
) -> tuple[AdviseRecord, ForecastRecord]:
    """Run the advise search and return ``(AdviseRecord, baseline ForecastRecord)``.

    ``model`` selects the lens: ``challenge`` (Monte-Carlo simulated search, the default),
    ``compromise`` (exact closed-form weighted-mean levers, D12.4), or ``both`` (challenge primary
    with the exact compromise lens attached as ``second_lens``, rendered side by side).

    Raises ``ValueError`` if ``advising_actor`` is not an actor in the game. ``grid_step`` sets the
    position sweep resolution; when ``None`` it is adaptive (span / 20). Salience steps at 5.
    """
    cfg = solver_config or SolverConfig()
    index = {a.id: i for i, a in enumerate(game.actors)}
    if advising_actor not in index:
        known = ", ".join(index)
        raise ValueError(f"actor {advising_actor!r} is not in this game (actors: {known}).")
    advisor_idx = index[advising_actor]
    ideal = game.actors[advisor_idx].position.mode

    pos_lo = min(a.position.low for a in game.actors)
    pos_hi = max(a.position.high for a in game.actors)
    pos_step = grid_step if grid_step is not None else max(round((pos_hi - pos_lo) / 20.0, 6), _EPS)
    sal_step = grid_step if grid_step is not None else 5.0

    def _maybe_enhance(lens: AdviseLens, settle: Settle, exact: bool) -> AdviseLens:
        if not strategy:
            return lens
        from schelling.advise.strategy import enhance_lens

        return enhance_lens(
            lens,
            game,
            advisor_idx,
            ideal,
            settle=settle,
            exact=exact,
            cfg=cfg,
            pos_step=pos_step,
            sal_step=sal_step,
            salience_floor=salience_floor,
            robustness_draws=robustness_draws,
            response_draws=response_draws,
            seed=seed,
            mode=mode,
        )

    def challenge_lens() -> tuple[AdviseLens, ForecastRecord]:
        base_rec = forecast(game, cfg, n_draws=target_draws, seed=seed, write=False)
        base_final = base_rec.ensemble.median
        base_lite = _median(game, cfg, draws_per_candidate, seed)
        om, tm, tg = _lens_moves(
            game,
            advisor_idx,
            ideal,
            lambda g: _median(g, cfg, draws_per_candidate, seed),
            lambda g: _median(g, cfg, target_draws, seed),
            base_lite,
            base_final,
            pos_step,
            sal_step,
            salience_floor,
        )
        lens = AdviseLens(
            model="challenge",
            exact=False,
            baseline_median=base_final,
            own_moves=om,
            top_moves=tm,
            persuasion_targets=tg,
        )
        lens = _maybe_enhance(lens, lambda g: _median(g, cfg, response_draws, seed), exact=False)
        return lens, base_rec

    def compromise_lens() -> tuple[AdviseLens, ForecastRecord]:
        base_rec = forecast(
            game, cfg, n_draws=target_draws, seed=seed, write=False, model="compromise"
        )
        base = _compromise_settlement(game)
        om, tm, tg = _lens_moves(
            game,
            advisor_idx,
            ideal,
            _compromise_settlement,
            _compromise_settlement,
            base,
            base,
            pos_step,
            sal_step,
            salience_floor,
        )
        lens = AdviseLens(
            model="compromise",
            exact=True,
            baseline_median=base,
            own_moves=om,
            top_moves=tm,
            persuasion_targets=tg,
        )
        lens = _maybe_enhance(lens, _compromise_settlement, exact=True)
        return lens, base_rec

    second: AdviseLens | None = None
    if model == "compromise":
        primary, baseline_record = compromise_lens()
    elif model == "both":
        primary, baseline_record = challenge_lens()
        second, _ = compromise_lens()
    else:
        primary, baseline_record = challenge_lens()

    advise_cfg: dict[str, str | float | int | bool | None] = {
        "model": model,
        "mode": mode,
        "strategy": strategy,
        "draws_per_candidate": draws_per_candidate,
        "target_draws": target_draws,
        "grid_step": pos_step,
        "salience_step": sal_step,
        "salience_floor": salience_floor,
        "robustness_draws": robustness_draws,
        "response_draws": response_draws,
    }
    hashed = _inputs_hash(game, cfg, advise_cfg, advising_actor)
    run_id = f"{game.question_id}-advise-{model}-{advising_actor}-s{seed}-{hashed[:12]}"

    brief = ""
    if strategy:
        from schelling.advise.strategy import strategy_brief

        brief = strategy_brief(
            advising_actor,
            ideal,
            primary.baseline_median,
            primary.top_moves[0] if primary.top_moves else None,
            primary.persuasion_targets[0] if primary.persuasion_targets else None,
            primary.equilibrium,
        )

    record = AdviseRecord(
        question_id=game.question_id,
        run_id=run_id,
        engine_version=engine_version(),
        inputs_hash=hashed,
        seed=seed,
        created_at=created_at,
        advising_actor=advising_actor,
        ideal=ideal,
        baseline_median=primary.baseline_median,
        baseline_run_id=baseline_record.run_id,
        advise_config=advise_cfg,
        solver_config=cfg.model_dump(mode="json"),
        model=primary.model,
        exact=primary.exact,
        own_moves=primary.own_moves,
        top_moves=primary.top_moves,
        persuasion_targets=primary.persuasion_targets,
        second_lens=second,
        mode=mode,
        strategy_brief=brief,
        equilibrium=primary.equilibrium,
        packages=primary.packages,
        game=game,
    )
    return record, baseline_record
