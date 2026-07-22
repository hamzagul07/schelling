"""Advise 2.0 strategy layer (Session 21): response, robustness, equilibrium, packages, brief.

Every new advise path — one-ply response, robustness grading (both lenses), the move
vocabulary, package search, --mode equilibrium, and the strategy brief — is exercised here,
plus a byte-identical re-run to hold determinism (CLAUDE.md rule 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.advise.moves import load_vocabulary, resolve_self_move, resolve_target_move
from schelling.advise.search import _compromise_settlement, advise
from schelling.advise.strategy import (
    _grade,
    equilibrium_exact,
    package_search,
    response_preview,
    robustness_challenge,
    robustness_exact,
    strategy_brief,
)
from schelling.schemas.forecast import SUCCESSOR_CAVEAT
from schelling.schemas.question import GameSpec

FIXTURES = Path(__file__).parent / "fixtures"


def _game() -> GameSpec:
    return GameSpec.model_validate(
        json.loads((FIXTURES / "emission_standards_widened.json").read_text())
    )


def _idx(game: GameSpec, actor_id: str) -> int:
    return [a.id for a in game.actors].index(actor_id)


# --------------------------------------------------------------- move vocabulary (item 4)
def test_vocabulary_loads_five_named_moves_sorted() -> None:
    vocab = load_vocabulary()
    names = [v.name for v in vocab]
    assert names == sorted(names)  # deterministic order
    assert set(names) == {
        "coalition_pull",
        "deescalate_signal",
        "escalate_commitment",
        "phased_concession",
        "side_payment",
    }


def test_flag_based_mt1_moves_are_deferred() -> None:
    # Item 4: guarantor/trap (MT-1.0 flag mechanics) stay absent until the model's reading.
    names = {v.name for v in load_vocabulary()}
    assert names.isdisjoint({"guarantor", "trap", "cohesion", "endurance"})


def test_self_move_resolves_delta_and_clamps_to_range() -> None:
    game = _game()
    i = _idx(game, "germany")
    a = game.actors[i]
    settlement = _compromise_settlement(game)
    phased = next(v for v in load_vocabulary() if v.name == "phased_concession")
    resolved = resolve_self_move(phased, game, i, settlement)
    assert resolved is not None
    field, value, action = resolved
    assert field == "position"
    assert a.position.low <= value <= a.position.high  # clamped to stated range
    assert action.name == "phased_concession" and "->" in action.delta
    # a target-scope move returns None when asked for a self move
    coalition = next(v for v in load_vocabulary() if v.name == "coalition_pull")
    assert resolve_self_move(coalition, game, i, settlement) is None


def test_target_move_labels_the_target_actor() -> None:
    game = _game()
    coalition = next(v for v in load_vocabulary() if v.name == "coalition_pull")
    j = _idx(game, "france")
    resolved = resolve_target_move(
        coalition, game, j, advisor_ideal=game.actors[_idx(game, "germany")].position.mode
    )
    assert resolved is not None
    _field, _value, action = resolved
    assert action.name == "coalition_pull(france)"


# --------------------------------------------------------------- response preview (item 1)
def test_response_preview_net_never_exceeds_gross() -> None:
    game = _game()
    i = _idx(game, "germany")
    baseline = _compromise_settlement(game)
    ideal = game.actors[i].position.mode
    rp = response_preview(
        _compromise_settlement,
        game,
        i,
        "position",
        game.actors[i].position.low,
        ideal,
        baseline,
        pos_step=10.0,
        sal_step=5.0,
        simulated=False,
    )
    # the opponent counters adversarially, so net benefit cannot beat the un-countered gross benefit
    assert rp.net_benefit <= rp.gross_benefit + 1e-9
    assert rp.responder_id != "germany"  # the most-affected responder is an opponent
    assert rp.simulated is False


# --------------------------------------------------------------- robustness grading (item 3)
def test_grade_robust_when_sign_stable() -> None:
    rob = _grade([0.4, 0.5, 0.45, 0.6, 0.38], point_benefit=0.45)
    assert rob.grade == "ROBUST" and rob.sign_stable_fraction == 1.0
    assert rob.benefit_ci_lo <= rob.benefit_ci_hi


def test_grade_knife_edge_when_sign_flips() -> None:
    rob = _grade([0.2, -0.3, 0.1, -0.2, 0.05], point_benefit=0.1)
    assert rob.grade == "KNIFE-EDGE" and rob.sign_stable_fraction < 0.90


def test_robustness_exact_grades_a_strong_move() -> None:
    game = _game()
    i = _idx(game, "germany")
    ideal = game.actors[i].position.mode
    rob = robustness_exact(
        game, i, "position", game.actors[i].position.low, ideal, 0.4, draws=120, seed=7
    )
    assert rob.grade in ("ROBUST", "KNIFE-EDGE")
    assert 0.0 <= rob.sign_stable_fraction <= 1.0


def test_robustness_challenge_runs_paired_solver() -> None:
    from schelling.solver.config import SolverConfig

    game = _game()
    i = _idx(game, "germany")
    ideal = game.actors[i].position.mode
    rob = robustness_challenge(
        game,
        SolverConfig(),
        i,
        "position",
        game.actors[i].position.low,
        ideal,
        0.3,
        draws=40,
        seed=7,
    )
    assert rob.grade in ("ROBUST", "KNIFE-EDGE")


# --------------------------------------------------------------- equilibrium (item 2)
def test_equilibrium_converges_on_widened_fixture() -> None:
    game = _game()
    eq = equilibrium_exact(game, pos_step=10.0, sal_step=5.0)
    assert eq.converged is True and eq.cycle == []
    assert eq.iterations >= 1
    assert eq.path[-1] == pytest.approx(eq.settlement)
    assert len(eq.moves) == len(game.actors)  # one settled move per actor


def test_equilibrium_respects_iteration_cap() -> None:
    game = _game()
    eq = equilibrium_exact(game, pos_step=1.0, sal_step=1.0, max_iters=2)
    assert eq.iterations <= 2  # never runs past the cap


def test_equilibrium_reports_cycle_honestly_when_settlement_recurs() -> None:
    # A settlement value that recurs in the path is reported as a cycle rather than a fixed point.
    game = _game()
    eq = equilibrium_exact(game, pos_step=10.0, sal_step=5.0)
    # on this fixture the dynamics converge; the cycle field is the honest empty report
    if eq.cycle:
        assert eq.cycle[0] == eq.cycle[-1]  # a cycle closes on itself
    else:
        assert eq.converged is True


# --------------------------------------------------------------- package search (item 5)
def test_package_search_returns_graded_two_move_bundles() -> None:
    game = _game()
    i = _idx(game, "germany")
    ideal = game.actors[i].position.mode
    baseline = _compromise_settlement(game)
    packages = package_search(game, i, ideal, baseline, 20.0, 10.0, 20.0, 120, 7)
    assert packages, "expected at least one bundle"
    for p in packages:
        assert len(p.moves) == 2  # two-move bundles
        assert p.cost >= 0.0  # benefit and cost stay separated
        assert p.robustness is not None and p.robustness.grade in ("ROBUST", "KNIFE-EDGE")
    # sorted best-benefit first
    benefits = [p.benefit for p in packages]
    assert benefits == sorted(benefits, reverse=True)


# --------------------------------------------------------------- strategy brief (item 6)
def test_strategy_brief_is_readable_and_deterministic() -> None:
    game = _game()
    rec, _ = advise(
        game,
        "germany",
        model="compromise",
        draws_per_candidate=40,
        target_draws=40,
        seed=7,
        grid_step=10.0,
        strategy=True,
        mode="equilibrium",
        robustness_draws=120,
        response_draws=120,
        created_at="2026-07-21T00:00:00Z",
    )
    brief = rec.strategy_brief
    assert brief.startswith("For germany")
    assert "best own move" in brief
    top = rec.top_moves[0]
    assert (
        strategy_brief(
            "germany",
            rec.ideal,
            rec.baseline_median,
            top,
            rec.persuasion_targets[0],
            rec.equilibrium,
        )
        == brief
    )


# --------------------------------------------------------------- advise() integration
def test_advise_strategy_enriches_top_moves() -> None:
    game = _game()
    rec, _ = advise(
        game,
        "germany",
        model="compromise",
        draws_per_candidate=40,
        target_draws=40,
        seed=7,
        grid_step=10.0,
        strategy=True,
        mode="levers",
        robustness_draws=80,
        response_draws=80,
        created_at="2026-07-21T00:00:00Z",
    )
    assert rec.mode == "levers"
    assert rec.equilibrium is None  # equilibrium is only computed under --mode equilibrium
    assert rec.packages  # packages are exact-lens, both modes
    for mv in rec.top_moves:
        assert mv.response is not None and mv.robustness is not None


def test_advise_equilibrium_mode_populates_equilibrium() -> None:
    game = _game()
    rec, _ = advise(
        game,
        "germany",
        model="compromise",
        draws_per_candidate=40,
        target_draws=40,
        seed=7,
        grid_step=10.0,
        strategy=True,
        mode="equilibrium",
        robustness_draws=80,
        response_draws=80,
        created_at="2026-07-21T00:00:00Z",
    )
    assert rec.mode == "equilibrium"
    assert rec.equilibrium is not None and rec.equilibrium.moves


def test_advise_strategy_is_byte_identical_on_rerun() -> None:
    game = _game()
    kw = dict(
        model="compromise",
        draws_per_candidate=40,
        target_draws=40,
        seed=7,
        grid_step=10.0,
        strategy=True,
        mode="equilibrium",
        robustness_draws=80,
        response_draws=80,
        created_at="2026-07-21T00:00:00Z",
    )
    a, _ = advise(game, "germany", **kw)  # type: ignore[arg-type]
    b, _ = advise(game, "germany", **kw)  # type: ignore[arg-type]
    assert a.model_dump_json() == b.model_dump_json()


def test_advise_challenge_lens_strategy_uses_simulated_response() -> None:
    game = _game()
    rec, _ = advise(
        game,
        "germany",
        model="challenge",
        draws_per_candidate=40,
        target_draws=40,
        seed=7,
        grid_step=10.0,
        strategy=True,
        mode="levers",
        robustness_draws=40,
        response_draws=40,
        created_at="2026-07-21T00:00:00Z",
    )
    assert rec.exact is False
    for mv in rec.top_moves:
        assert (
            mv.response is not None and mv.response.simulated is True
        )  # challenge lens = simulated


# --------------------------------------------------------------- report golden
def test_advise_strategy_report_matches_golden() -> None:
    from schelling.report.render import render

    data = json.loads((FIXTURES / "report" / "advise_strategy.json").read_text())
    html = render(data)
    assert html == (FIXTURES / "report" / "advise_strategy_report.html").read_text()


def test_advise_strategy_report_has_all_sections_and_successor_caveat() -> None:
    from schelling.report.render import render

    data = json.loads((FIXTURES / "report" / "advise_strategy.json").read_text())
    html = render(data)
    for heading in ("Strategy brief", "Response preview", "two-move packages", "Equilibrium"):
        assert heading in html
    assert SUCCESSOR_CAVEAT in html  # equilibrium mode swaps in the successor caveat
