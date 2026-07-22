"""The strategy layer (Advise 2.0): response previews, robustness, equilibrium, packages.

All exact-lens machinery is closed-form on the compromise weighted mean; the challenge lens is
simulated at reduced draws and labeled. Everything is deterministic under the same derived seeds
(CLAUDE.md rule 2). ``search.advise`` calls into here to enrich its lever tables.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from schelling.advise.moves import load_vocabulary, resolve_self_move
from schelling.advise.search import _compromise_settlement, _grid, _set_point
from schelling.mc.monte_carlo import run_monte_carlo
from schelling.mc.sampling import derive_rng, sample_game
from schelling.schemas.forecast import (
    AdviseLens,
    EquilibriumMove,
    EquilibriumResult,
    MovePackage,
    OwnMove,
    PersuasionTarget,
    ResponsePreview,
    Robustness,
)
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig

Settle = Callable[[GameSpec], float]
_EPS = 1e-9


def _benefit(after: float, before: float, ideal: float) -> float:
    return abs(before - ideal) - abs(after - ideal)


# ------------------------------------------------------- best response (within stated ranges)
def _candidates(
    game: GameSpec, idx: int, pos_step: float, sal_step: float
) -> list[tuple[str, float]]:
    a = game.actors[idx]
    cands = [("position", v) for v in _grid(a.position.low, a.position.high, pos_step)]
    cands += [("salience", v) for v in _grid(a.salience.low, a.salience.high, sal_step)]
    return cands


def _best_response(
    settle: Settle,
    game: GameSpec,
    idx: int,
    objective: Callable[[float], float],
    pos_step: float,
    sal_step: float,
) -> tuple[str | None, float, float]:
    """Best single move for actor ``idx`` minimizing ``objective``; None field = no move."""
    base = settle(game)
    best_field: str | None = None
    best_val = game.actors[idx].position.mode
    best_score = objective(base)
    best_settle = base
    for field, v in _candidates(game, idx, pos_step, sal_step):
        s = settle(_set_point(game, idx, field, v))
        score = objective(s)
        if score < best_score - _EPS:
            best_field, best_val, best_score, best_settle = field, v, score, s
    return best_field, best_val, best_settle


# --------------------------------------------------------------- one-ply response preview (item 1)
def response_preview(
    settle: Settle,
    game: GameSpec,
    advisor_idx: int,
    move_field: str,
    move_value: float,
    ideal: float,
    baseline: float,
    pos_step: float,
    sal_step: float,
    *,
    simulated: bool,
) -> ResponsePreview:
    """Gross benefit vs net after the most-affected opponent's best single counter-response."""
    moved = _set_point(game, advisor_idx, move_field, move_value)
    gross = _benefit(settle(moved), baseline, ideal)
    worst_net: float | None = None
    worst: tuple[str, str | None, float] | None = None
    for j in range(len(game.actors)):
        if j == advisor_idx:
            continue
        # the opponent counters adversarially: maximize distance of the settlement from the advisor
        field, val, s = _best_response(
            settle, moved, j, lambda x: -abs(x - ideal), pos_step, sal_step
        )
        net = _benefit(s, baseline, ideal)
        if worst_net is None or net < worst_net:
            worst_net, worst = net, (game.actors[j].id, field, val)
    assert worst is not None and worst_net is not None
    rid, rfield, rval = worst
    move_str = "no profitable counter" if rfield is None else f"{rfield} -> {rval:g}"
    return ResponsePreview(
        responder_id=rid,
        responder_move=move_str,
        gross_benefit=gross,
        net_benefit=worst_net,
        simulated=simulated,
    )


# --------------------------------------------------------------- robustness grading (item 3)
def _grade(benefits: list[float], point_benefit: float) -> Robustness:
    arr = np.asarray(benefits, dtype=float)
    lo, hi = (float(x) for x in np.percentile(arr, [10.0, 90.0]))
    ref = 1.0 if point_benefit > _EPS else (-1.0 if point_benefit < -_EPS else 0.0)
    if ref == 0.0:
        stable = float(np.mean(np.abs(arr) < 1e-6))
    else:
        stable = float(np.mean(np.sign(arr) == ref))
    return Robustness(
        benefit_ci_lo=lo,
        benefit_ci_hi=hi,
        sign_stable_fraction=stable,
        grade="ROBUST" if stable >= 0.90 else "KNIFE-EDGE",
    )


def robustness_exact(
    game: GameSpec,
    actor_idx: int,
    field: str,
    value: float,
    ideal: float,
    point_benefit: float,
    draws: int,
    seed: int,
) -> Robustness:
    """Grade a move's benefit across MC draws of the triangular inputs (exact weighted mean)."""
    benefits: list[float] = []
    for i in range(draws):
        sampled = sample_game(game, derive_rng(seed, i))
        base = _compromise_settlement(sampled)
        moved = _compromise_settlement(_set_point(sampled, actor_idx, field, value))
        benefits.append(_benefit(moved, base, ideal))
    return _grade(benefits, point_benefit)


def robustness_challenge(
    game: GameSpec,
    cfg: SolverConfig,
    actor_idx: int,
    field: str,
    value: float,
    ideal: float,
    point_benefit: float,
    draws: int,
    seed: int,
) -> Robustness:
    """Grade via paired MC solver runs (baseline vs moved) at reduced draws."""
    base_d = run_monte_carlo(game, cfg, n_draws=draws, seed=seed).median_distribution
    moved_d = run_monte_carlo(
        _set_point(game, actor_idx, field, value), cfg, n_draws=draws, seed=seed
    ).median_distribution
    benefits = [_benefit(float(m), float(b), ideal) for b, m in zip(base_d, moved_d, strict=True)]
    return _grade(benefits, point_benefit)


# --------------------------------------------------------------- equilibrium (item 2, exact only)
def equilibrium_exact(
    game: GameSpec, pos_step: float, sal_step: float, *, max_iters: int = 25
) -> EquilibriumResult:
    """Iterated best responses (each actor -> its ideal) to a fixed point or a reported cycle."""
    ideals = [a.position.mode for a in game.actors]
    origin = [(a.position.mode, a.salience.mode) for a in game.actors]
    current = game
    path = [round(_compromise_settlement(current), 6)]
    converged = False
    cycle: list[float] = []
    iterations = 0
    for it in range(max_iters):
        iterations = it + 1
        changed = False
        for i in range(len(current.actors)):
            obj = (lambda idl: lambda s: abs(s - idl))(ideals[i])
            field, val, _ = _best_response(
                _compromise_settlement, current, i, obj, pos_step, sal_step
            )
            if field is not None:
                current = _set_point(current, i, field, val)
                changed = True
        s = round(_compromise_settlement(current), 6)
        if not changed:  # fixed point
            path.append(s)
            converged = True
            break
        if s in path:  # settlement value recurred -> honest cycle report
            cycle = [*path[path.index(s) :], s]
            path.append(s)
            break
        path.append(s)
    moves = [
        EquilibriumMove(
            actor_id=current.actors[i].id,
            position_from=origin[i][0],
            position_to=current.actors[i].position.mode,
            salience_from=origin[i][1],
            salience_to=current.actors[i].salience.mode,
        )
        for i in range(len(current.actors))
    ]
    return EquilibriumResult(
        settlement=path[-1],
        converged=converged,
        iterations=iterations,
        path=path,
        cycle=cycle,
        moves=moves,
    )


# ----------------------------------------------------- package search (item 5, exact only)
@dataclass(frozen=True)
class _Cand:
    actor: int
    field: str
    value: float
    cost: float
    desc: str


def _package_candidates(
    game: GameSpec,
    advisor_idx: int,
    ideal: float,
    coarse_pos: float,
    coarse_sal: float,
    salience_floor: float,
) -> list[_Cand]:
    advisor = game.actors[advisor_idx]
    cands: list[_Cand] = []
    for v in _grid(advisor.position.low, advisor.position.high, coarse_pos):
        cands.append(_Cand(advisor_idx, "position", v, abs(v - ideal), f"own position -> {v:g}"))
    for v in _grid(salience_floor, 100.0, coarse_sal):
        cands.append(_Cand(advisor_idx, "salience", v, 0.0, f"own salience -> {v:g}"))
    for j, a in enumerate(game.actors):
        if j == advisor_idx:
            continue
        to_pos = a.position.high if ideal >= a.position.mode else a.position.low
        cands.append(_Cand(j, "position", to_pos, 0.0, f"persuade {a.id}.position -> {to_pos:g}"))
    for vm in load_vocabulary():
        resolved = resolve_self_move(vm, game, advisor_idx, _compromise_settlement(game))
        if resolved is not None:
            field, value, action = resolved
            cost = abs(value - ideal) if field == "position" else 0.0
            cands.append(_Cand(advisor_idx, field, value, cost, action.name))
    return cands


def package_search(
    game: GameSpec,
    advisor_idx: int,
    ideal: float,
    baseline: float,
    coarse_pos: float,
    coarse_sal: float,
    salience_floor: float,
    robustness_draws: int,
    seed: int,
    *,
    top: int = 3,
) -> list[MovePackage]:
    """Best two-move bundles under the exact lens, benefit/cost separated, robustness-graded."""
    cands = _package_candidates(game, advisor_idx, ideal, coarse_pos, coarse_sal, salience_floor)
    scored: list[tuple[float, float, float, list[str]]] = []
    for i in range(len(cands)):
        for k in range(i + 1, len(cands)):
            ca, cb = cands[i], cands[k]
            if (ca.actor, ca.field) == (cb.actor, cb.field):
                continue  # the same lever twice is not a bundle
            g2 = _set_point(
                _set_point(game, ca.actor, ca.field, ca.value), cb.actor, cb.field, cb.value
            )
            s = _compromise_settlement(g2)
            scored.append((_benefit(s, baseline, ideal), ca.cost + cb.cost, s, [ca.desc, cb.desc]))
    scored.sort(key=lambda p: (-p[0], p[1], p[3]))
    packages: list[MovePackage] = []
    for benefit, cost, settle, descs in scored[:top]:
        chosen = [next(c for c in cands if c.desc == d) for d in descs]
        packages.append(
            MovePackage(
                moves=descs,
                settlement_median=settle,
                benefit=benefit,
                cost=cost,
                robustness=_grade(
                    _pair_benefits(game, chosen, ideal, robustness_draws, seed), benefit
                ),
            )
        )
    return packages


def _pair_benefits(
    game: GameSpec, chosen: list[_Cand], ideal: float, draws: int, seed: int
) -> list[float]:
    benefits: list[float] = []
    for i in range(draws):
        g2 = sampled = sample_game(game, derive_rng(seed, i))
        base = _compromise_settlement(sampled)
        for c in chosen:
            g2 = _set_point(g2, c.actor, c.field, c.value)
        benefits.append(_benefit(_compromise_settlement(g2), base, ideal))
    return benefits


# --------------------------------------------------------------- lens enrichment orchestration
def _vocab_own_moves(
    game: GameSpec, advisor_idx: int, ideal: float, baseline: float, settle: Settle
) -> list[OwnMove]:
    """Vocabulary self-moves as OwnMove candidates carrying their MoveAction (item 4)."""
    advisor = game.actors[advisor_idx]
    moves: list[OwnMove] = []
    settlement_now = settle(game)
    for vm in load_vocabulary():
        resolved = resolve_self_move(vm, game, advisor_idx, settlement_now)
        if resolved is None:
            continue
        field, value, action = resolved
        m = settle(_set_point(game, advisor_idx, field, value))
        est = advisor.position if field == "position" else advisor.salience
        moves.append(
            OwnMove(
                dimension=field,
                value=value,
                settlement_median=m,
                benefit=_benefit(m, baseline, ideal),
                cost=abs(value - ideal) if field == "position" else 0.0,
                beyond_stated_range=not (est.low <= value <= est.high),
                action=action,
            )
        )
    return moves


def enhance_lens(
    lens: AdviseLens,
    game: GameSpec,
    advisor_idx: int,
    ideal: float,
    *,
    settle: Settle,
    exact: bool,
    cfg: SolverConfig,
    pos_step: float,
    sal_step: float,
    salience_floor: float,
    robustness_draws: int,
    response_draws: int,
    seed: int,
    mode: str,
) -> AdviseLens:
    """Enrich a lens with vocab moves, one-ply responses, robustness, packages, and equilibrium."""
    baseline = lens.baseline_median
    # merge sweep top moves with vocabulary self-moves, re-rank, keep the best three
    pool = list(lens.top_moves) + _vocab_own_moves(game, advisor_idx, ideal, baseline, settle)
    pool.sort(key=lambda mv: (-mv.benefit, mv.cost, mv.dimension, mv.value))
    top: list[OwnMove] = []
    for mv in pool[:3]:
        rob = (
            robustness_exact(
                game, advisor_idx, mv.dimension, mv.value, ideal, mv.benefit, robustness_draws, seed
            )
            if exact
            else robustness_challenge(
                game,
                cfg,
                advisor_idx,
                mv.dimension,
                mv.value,
                ideal,
                mv.benefit,
                robustness_draws,
                seed,
            )
        )
        resp = response_preview(
            settle,
            game,
            advisor_idx,
            mv.dimension,
            mv.value,
            ideal,
            baseline,
            pos_step,
            sal_step,
            simulated=not exact,
        )
        top.append(mv.model_copy(update={"response": resp, "robustness": rob}))

    targets = []
    for t in lens.persuasion_targets[:3]:
        j = next(i for i, a in enumerate(game.actors) if a.id == t.actor_id)
        rob = (
            robustness_exact(
                game, j, t.dimension, t.to_value, ideal, t.benefit, robustness_draws, seed
            )
            if exact
            else robustness_challenge(
                game, cfg, j, t.dimension, t.to_value, ideal, t.benefit, robustness_draws, seed
            )
        )
        targets.append(t.model_copy(update={"robustness": rob}))
    targets += list(lens.persuasion_targets[3:])

    equilibrium = None
    packages: list[MovePackage] = []
    if exact:  # equilibrium and package search are exact-lens only (spec)
        packages = package_search(
            game,
            advisor_idx,
            ideal,
            baseline,
            pos_step * 2,
            sal_step * 2,
            salience_floor,
            robustness_draws,
            seed,
        )
        if mode == "equilibrium":
            equilibrium = equilibrium_exact(game, pos_step, sal_step)

    return lens.model_copy(
        update={
            "top_moves": top,
            "persuasion_targets": targets,
            "packages": packages,
            "equilibrium": equilibrium,
        }
    )


# --------------------------------------------------------------- strategy brief (item 6)
def strategy_brief(
    advising_actor: str,
    ideal: float,
    baseline: float,
    top_move: OwnMove | None,
    top_target: PersuasionTarget | None,
    equilibrium: EquilibriumResult | None,
) -> str:
    """A deterministic, readable one-paragraph brief for the advised actor (item 6)."""
    parts = [f"For {advising_actor} (ideal {ideal:g}, baseline settlement {baseline:.1f}):"]
    if top_move is not None:
        mv = top_move
        action = f" ({mv.action.name})" if mv.action else ""
        piece = f" best own move {mv.dimension} -> {mv.value:g}{action} (benefit {mv.benefit:+.1f}"
        if mv.response is not None:
            piece += (
                f", net {mv.response.net_benefit:+.1f} after "
                f"{mv.response.responder_id}'s best response"
            )
        if mv.robustness is not None:
            piece += f", {mv.robustness.grade}"
        parts.append(piece + ")")
    if top_target is not None:
        t = top_target
        parts.append(
            f"; the best actor to work on is {t.actor_id} "
            f"({t.kind} its {t.dimension}, benefit {t.benefit:+.1f})"
        )
    if equilibrium is not None:
        tail = " (a cycle, not a fixed point)" if equilibrium.cycle else ""
        parts.append(
            ". Under model-optimal play by all actors the settlement settles near "
            f"{equilibrium.settlement:.1f}{tail}"
        )
    return "".join(parts) + "."
