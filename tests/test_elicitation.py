"""Elicitation ensembles (Session 45, D45): reconciliation and variance decomposition.

The variance test carries the true shares worked out by hand on an additive fixture; the
reconciliation tests check widening (never narrows), minority retention, and per-actor agreement.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from schelling.elicitation.ensemble import run_ensemble
from schelling.elicitation.reconcile import reconcile
from schelling.elicitation.variance import decompose_question, variance_shares
from schelling.formalizer.client import LLMResult, ReplayClient
from schelling.mc.monte_carlo import forecast
from schelling.report.render import render_forecast
from schelling.schemas.elicitation import (
    ActorAgreement,
    CoordinateAgreement,
    ElicitationSummary,
    VarianceShares,
)
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor, TriangularEstimate

FIXTURES = Path(__file__).parent / "fixtures"
SITUATION = "Three regional powers negotiate a phase-out year; one is the most powerful."


def _actor(aid: str, pos: TriangularEstimate, *, sal: float = 50.0, cap: float = 50.0) -> Actor:
    return Actor(
        id=aid,
        name=aid.upper(),
        position=pos,
        salience=TriangularEstimate.point(sal),
        capability=TriangularEstimate.point(cap),
        evidence=[],
    )


def _game(actors: list[Actor]) -> GameSpec:
    return GameSpec(
        question_id="Q",
        frozen_at="2026-07-28",
        continuum=Continuum(label="l", anchor_0="0", anchor_100="100"),
        actors=actors,
        template="t",
        horizon="h",
    )


def _tri(lo: float, mo: float, hi: float) -> TriangularEstimate:
    return TriangularEstimate(low=lo, mode=mo, high=hi)


# --------------------------------------------------------------- variance decomposition (D45.3)
def test_variance_shares_additive_fixture_by_hand() -> None:
    # f[i,j,k] = a[i] + c[j] + b[k], independent additive components:
    #   a = [0, 10]  (drafts)  -> Var 25   -> elicitation
    #   c = [0, 4]   (models)  -> Var 4    -> model choice
    #   b = [-1, 1]  (samples) -> Var 1    -> input ranges
    # total variance 30; shares 25/30, 4/30, 1/30.
    a = np.array([0.0, 10.0])
    c = np.array([0.0, 4.0])
    b = np.array([-1.0, 1.0])
    f = a[:, None, None] + c[None, :, None] + b[None, None, :]  # (2, 2, 2)
    shares = variance_shares(f)
    assert shares.total_variance == pytest.approx(30.0)
    assert shares.elicitation == pytest.approx(25.0 / 30.0)
    assert shares.model_choice == pytest.approx(4.0 / 30.0)
    assert shares.input_ranges == pytest.approx(1.0 / 30.0)


def test_variance_shares_sum_to_one() -> None:
    rng = np.random.default_rng(0)
    f = rng.normal(size=(4, 3, 200))
    shares = variance_shares(f)
    assert shares.elicitation + shares.input_ranges + shares.model_choice == pytest.approx(1.0)
    assert all(
        0.0 <= s <= 1.0 for s in (shares.elicitation, shares.input_ranges, shares.model_choice)
    )


def test_variance_shares_constant_grid_is_all_zero() -> None:
    shares = variance_shares(np.full((3, 2, 50), 42.0))
    assert (shares.elicitation, shares.input_ranges, shares.model_choice) == (0.0, 0.0, 0.0)


def test_decompose_question_over_solvers_sums_to_one() -> None:
    # two drafts that disagree, decomposed over two solvers; shares must still sum to 1.
    d1 = _game([_actor("a", _tri(20, 30, 40)), _actor("b", _tri(60, 70, 80))])
    d2 = _game([_actor("a", _tri(40, 50, 60)), _actor("b", _tri(50, 60, 70))])
    shares = decompose_question([d1, d2], ["challenge", "compromise"], n_draws=300, seed=1)
    assert shares.elicitation + shares.input_ranges + shares.model_choice == pytest.approx(1.0)
    assert "law-of-total-variance" in shares.method


# --------------------------------------------------------------- reconciliation (D45.2)
def test_reconcile_widens_to_span_disagreement() -> None:
    # actor A: draft1 says 25-30-35, draft2 says 65-70-75, draft3 says 45-50-55
    d1 = _game([_actor("a", _tri(25, 30, 35)), _actor("b", _tri(45, 50, 55))])
    d2 = _game([_actor("a", _tri(65, 70, 75)), _actor("b", _tri(48, 52, 56))])
    d3 = _game([_actor("a", _tri(45, 50, 55)), _actor("c", _tri(35, 40, 45))])
    consensus, summary = reconcile([d1, d2, d3], draft_hashes=["h1", "h2", "h3"])
    a = next(x for x in consensus.actors if x.id == "a")
    # widened to [min low, max high] = [25, 75], mode = median(30,70,50) = 50
    assert (a.position.low, a.position.mode, a.position.high) == (25.0, 50.0, 75.0)
    ag = next(x for x in summary.actors if x.actor_id == "a")
    assert ag.present_in == 3 and ag.n_drafts == 3 and ag.low_presence is False
    pos = next(c for c in ag.coordinates if c.field == "position")
    assert pos.mode_spread == pytest.approx(40.0)  # 70 - 30
    assert summary.draft_hashes == ["h1", "h2", "h3"]


def test_reconcile_widening_never_narrows() -> None:
    d1 = _game([_actor("a", _tri(20, 30, 40))])
    d2 = _game([_actor("a", _tri(10, 35, 90))])  # a much wider draft
    consensus, _ = reconcile([d1, d2])
    a = consensus.actors[0]
    # consensus must contain BOTH drafts' ranges: low <= every low, high >= every high
    assert a.position.low <= 20.0 and a.position.low <= 10.0
    assert a.position.high >= 40.0 and a.position.high >= 90.0
    assert a.position.low == 10.0 and a.position.high == 90.0


def test_reconcile_keeps_minority_actors_flagged() -> None:
    # C appears in 1 of 3 drafts -> minority, retained and flagged, never dropped.
    d1 = _game([_actor("a", _tri(20, 30, 40)), _actor("b", _tri(50, 55, 60))])
    d2 = _game([_actor("a", _tri(30, 40, 50)), _actor("b", _tri(52, 57, 62))])
    d3 = _game([_actor("a", _tri(25, 35, 45)), _actor("c", _tri(70, 75, 80))])
    consensus, summary = reconcile([d1, d2, d3])
    ids = {x.id for x in consensus.actors}
    assert ids == {"a", "b", "c"}  # nothing dropped
    c_ag = next(x for x in summary.actors if x.actor_id == "c")
    assert c_ag.present_in == 1 and c_ag.low_presence is True
    b_ag = next(x for x in summary.actors if x.actor_id == "b")
    assert b_ag.present_in == 2 and b_ag.low_presence is False  # 2 of 3 is a majority
    assert "LOW PRESENCE" in consensus.actors[-1].evidence[0].note  # the flagged consensus actor
    assert "Low-presence actors" in (consensus.notes or "")


def test_reconcile_single_draft_is_a_passthrough() -> None:
    d1 = _game([_actor("a", _tri(20, 30, 40))])
    consensus, summary = reconcile([d1])
    a = consensus.actors[0]
    assert (a.position.low, a.position.mode, a.position.high) == (20.0, 30.0, 40.0)
    assert summary.actors[0].present_in == 1 and summary.actors[0].low_presence is False


# --------------------------------------------------------------- ensemble orchestration (D45.1)
def test_run_ensemble_makes_n_drafts_with_recorded_provenance() -> None:
    text = (FIXTURES / "formalize_replay.json").read_text()

    def client_for(_i: int, model: str) -> ReplayClient:
        return ReplayClient(responses=[LLMResult(text, 100, 50)], model_name=model)

    drafts = run_ensemble(SITUATION, n=3, models=["model-a", "model-b"], client_for=client_for)
    assert len(drafts) == 3
    assert [d.metadata.draft_index for d in drafts] == [0, 1, 2]
    # the judge model cycles and is recorded per draft
    assert [d.metadata.model for d in drafts] == ["model-a", "model-b", "model-a"]


# --------------------------------------------------------------- report panel + scope line (D45.4)
def _rubric() -> ResolutionRubric:
    return ResolutionRubric(
        resolution_criteria="c",
        adjudicating_sources=["s"],
        outcome_mapping="m",
        grading_formula="score = |median - actual|",
        bands=[
            RubricBand(lo=0.0, hi=50.0, label="low"),
            RubricBand(lo=51.0, hi=100.0, label="high"),
        ],
    )


def _summary() -> ElicitationSummary:
    coord = CoordinateAgreement(
        field="position",
        draft_modes=[30.0, 70.0],
        mode_spread=40.0,
        consensus_low=25.0,
        consensus_mode=50.0,
        consensus_high=75.0,
    )
    return ElicitationSummary(
        n_drafts=3,
        draft_hashes=["h1", "h2", "h3"],
        actors=[
            ActorAgreement(
                actor_id="a",
                name="A",
                present_in=3,
                n_drafts=3,
                low_presence=False,
                coordinates=[coord],
            ),
            ActorAgreement(
                actor_id="c",
                name="C",
                present_in=1,
                n_drafts=3,
                low_presence=True,
                coordinates=[coord],
            ),
        ],
        variance=VarianceShares(
            elicitation=0.5,
            input_ranges=0.2,
            model_choice=0.3,
            total_variance=100.0,
            method="nested law-of-total-variance",
        ),
    )


def _rubric_game() -> GameSpec:
    g = _game([_actor("a", _tri(20, 30, 40)), _actor("b", _tri(60, 70, 80))])
    return g.model_copy(update={"resolution_rubric": _rubric()})


def test_report_shows_panel_and_broadened_scope_with_elicitation() -> None:
    rec = forecast(_rubric_game(), n_draws=100, seed=1, write=False)
    html = render_forecast(rec.model_copy(update={"elicitation": _summary()}))
    assert "Elicitation uncertainty" in html  # the panel
    assert "present 1/3" not in html  # (rendered as "1/3" in a table cell)
    assert "1/3" in html and "low presence" in html  # minority actor disclosed
    # scope broadened only where measured: elicitation no longer disclaimed, coding error still is
    assert "all measured here" in html
    assert "coding error" in html
    assert "input ranges only" not in html


def test_report_default_scope_without_elicitation() -> None:
    rec = forecast(_rubric_game(), n_draws=100, seed=1, write=False)
    html = render_forecast(rec)
    assert "Elicitation uncertainty" not in html
    assert "input ranges only" in html  # the standing scope note is unchanged
