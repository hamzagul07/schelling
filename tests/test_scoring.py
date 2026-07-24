"""Proper scoring rules (Session 40, D40.1): Brier, logarithmic, CRPS, and the integrity
constraint that the three sealed questions keep |median - actual| as their primary metric.

The raw-rule tests carry values worked out **by hand** in the comments, per the milestone brief."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from schelling.backtest import scoring
from schelling.report.rubric_lookup import parse_rubric_block
from schelling.schemas.forecast import Ensemble, ForecastRecord
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor, TriangularEstimate

REPO_ROOT = Path(__file__).resolve().parent.parent

# The three questions sealed before D40 — their committed rubrics must keep abs-error primary.
SEALED_QUESTIONS = ("Q-2026-USIRAN-STAGE2", "Q-2026-IAEA-SEP", "Q-2026-OPEC-SEP")


def _actor() -> Actor:
    return Actor(
        id="a",
        name="A",
        position=TriangularEstimate.point(50.0),
        salience=TriangularEstimate.point(50.0),
        capability=TriangularEstimate.point(50.0),
        evidence=[],
    )


def _game(bands: list[RubricBand], *, primary_metric: str = "") -> GameSpec:
    rubric = ResolutionRubric(
        resolution_criteria="c",
        adjudicating_sources=["s"],
        outcome_mapping="m",
        grading_formula="score = |median - actual|",
        bands=bands,
        primary_metric=primary_metric,
        secondary_metrics=["absolute_error"] if primary_metric else [],
    )
    return GameSpec(
        question_id="Q-TEST",
        frozen_at="2026-07-24",
        continuum=Continuum(label="l", anchor_0="0", anchor_100="100"),
        actors=[_actor()],
        template="t",
        horizon="h",
        resolution_rubric=rubric,
    )


def _record(game: GameSpec | None, draws: list[float], median: float) -> ForecastRecord:
    xs = sorted(draws)
    n = len(xs)
    p10 = xs[max(0, int(0.1 * n) - 1)] if n else 0.0
    p90 = xs[min(n - 1, int(0.9 * n))] if n else 0.0
    return ForecastRecord(
        question_id="Q-TEST",
        run_id="r",
        inputs_hash="h",
        seed=0,
        ensemble=Ensemble(median=median, mean=median, p10=p10, p90=p90, n_draws=n),
        game=game,
        outcome_distribution=list(draws),
    )


_THREE_BANDS = [
    RubricBand(lo=0.0, hi=33.0, label="low"),
    RubricBand(lo=34.0, hi=66.0, label="mid"),
    RubricBand(lo=67.0, hi=100.0, label="high"),
]


# --------------------------------------------------------------- raw rules, verified by hand
def test_absolute_error() -> None:
    assert scoring.absolute_error(60.0, 50.0) == 10.0


def test_brier_by_hand() -> None:
    # probs [0.2, 0.5, 0.3], realized index 1:
    # (0.2-0)^2 + (0.5-1)^2 + (0.3-0)^2 = 0.04 + 0.25 + 0.09 = 0.38
    assert scoring.brier_score([0.2, 0.5, 0.3], 1) == pytest.approx(0.38)
    # a perfectly confident correct call scores 0; a confident wrong call scores 2
    assert scoring.brier_score([0.0, 1.0, 0.0], 1) == pytest.approx(0.0)
    assert scoring.brier_score([1.0, 0.0, 0.0], 1) == pytest.approx(2.0)


def test_log_score_by_hand() -> None:
    # ln(0.5) for the realized band's probability
    assert scoring.log_score([0.2, 0.5, 0.3], 1, floor=1e-9) == pytest.approx(math.log(0.5))
    # a perfect confident call scores 0 = ln(1)
    assert scoring.log_score([0.0, 1.0, 0.0], 1, floor=1e-9) == pytest.approx(0.0)
    # zero probability on the realized band is floored, not -inf
    assert scoring.log_score([0.5, 0.5, 0.0], 2, floor=1e-4) == pytest.approx(math.log(1e-4))


def test_crps_by_hand() -> None:
    # draws [0, 10], actual 4:
    #   E|X-y| = (|0-4| + |10-4|)/2 = (4+6)/2 = 5
    #   sum_{i,j}|x_i-x_j| = 0+10+10+0 = 20 ; spread = 20/(2*2^2) = 2.5
    #   CRPS = 5 - 2.5 = 2.5
    assert scoring.crps_empirical([0.0, 10.0], 4.0) == pytest.approx(2.5)


def test_crps_reduces_to_absolute_error_at_a_point_mass() -> None:
    # all draws equal -> spread term 0 -> CRPS == |forecast - actual| (the generalization claim)
    assert scoring.crps_empirical([2.0, 2.0, 2.0], 5.0) == pytest.approx(3.0)
    assert scoring.crps_empirical([7.0], 3.0) == pytest.approx(4.0)
    for m, y in ((10.0, 25.0), (63.68, 50.0), (0.0, 100.0)):
        assert scoring.crps_empirical([m] * 8, y) == pytest.approx(abs(m - y))


# --------------------------------------------------------------- score_record dispatch
def test_banded_record_gets_brier_and_log() -> None:
    # draws: 2 in low, 5 in mid, 3 in high -> probs [0.2, 0.5, 0.3]; actual 50 -> mid band
    draws = [10.0] * 2 + [50.0] * 5 + [80.0] * 3
    card = _record(_game(_THREE_BANDS), draws, median=50.0)
    result = scoring.score_record(card, actual=50.0)
    assert result.kind == "banded"
    assert result.realized_band == "mid"
    names = {s.name for s in result.scores}
    assert names == {"absolute_error", "brier", "log"}
    brier = next(s for s in result.scores if s.name == "brier")
    log = next(s for s in result.scores if s.name == "log")
    assert brier.value == pytest.approx(0.38)
    assert log.value == pytest.approx(math.log(0.5))


def test_arithmetic_record_gets_crps() -> None:
    card = _record(_game([]), [0.0, 10.0], median=5.0)
    result = scoring.score_record(card, actual=4.0)
    assert result.kind == "linear"
    crps = next(s for s in result.scores if s.name == "crps")
    assert crps.value == pytest.approx(2.5)
    assert "brier" not in {s.name for s in result.scores}


def test_undeclared_primary_defaults_to_absolute_error() -> None:
    # a banded rubric that declares no primary_metric keeps abs-error primary (the sealed behaviour)
    draws = [10.0] * 2 + [50.0] * 5 + [80.0] * 3
    result = scoring.score_record(_record(_game(_THREE_BANDS), draws, 50.0), actual=50.0)
    assert result.primary is not None
    assert result.primary.name == "absolute_error"
    assert {s.name for s in result.secondary} == {"brier", "log"}


def test_declared_primary_is_marked() -> None:
    draws = [10.0] * 2 + [50.0] * 5 + [80.0] * 3
    game = _game(_THREE_BANDS, primary_metric="brier")
    result = scoring.score_record(_record(game, draws, 50.0), actual=50.0)
    assert result.primary is not None and result.primary.name == "brier"
    assert "absolute_error" in {s.name for s in result.secondary}


def test_no_rubric_falls_back_to_absolute_error_primary() -> None:
    result = scoring.score_record(_record(None, [40.0, 60.0], 50.0), actual=55.0)
    assert result.kind == "none"
    assert result.primary is not None and result.primary.name == "absolute_error"


# --------------------------------------------------------------- runs loading / compare panel
def test_score_runs_skips_non_forecast_records(tmp_path: Path) -> None:
    game = _game([])
    rec = _record(game, [40.0, 60.0], 50.0).model_copy(
        update={"question_id": "Q-A", "run_id": "ra"}
    )
    (tmp_path / "ra.json").write_text(rec.model_dump_json())
    (tmp_path / "not-a-record.json").write_text('{"kind": "llm-judgment", "verdict": 58}')
    records = scoring.load_forecast_records(tmp_path)
    assert [r.run_id for r in records] == ["ra"]  # the bogus file is skipped
    cards = scoring.score_runs(records, {"Q-A": 55.0})
    assert len(cards) == 1 and cards[0].question_id == "Q-A"
    assert cards[0].primary is not None


# --------------------------------------------------------------- INTEGRITY CONSTRAINT (D40.1)
def test_sealed_rubrics_keep_absolute_error_primary() -> None:
    """No committed rubric's primary metric changes: each sealed question's rubric declares no
    proper-scoring primary, so it is graded on |median - actual| exactly as sealed (D40.1)."""
    for qid in SEALED_QUESTIONS:
        path = REPO_ROOT / f"GRADING-{qid}.md"
        assert path.exists(), f"missing committed grading file for {qid}"
        rubric = parse_rubric_block(path.read_text())
        assert rubric is not None, f"no machine-readable rubric in GRADING-{qid}.md"
        assert rubric.primary_metric == "", f"{qid} must not declare a proper-scoring primary"
        assert scoring.primary(rubric) == "absolute_error"
        assert "median" in rubric.grading_formula and "actual" in rubric.grading_formula
