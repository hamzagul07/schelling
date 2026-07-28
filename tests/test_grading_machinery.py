"""Grading machinery — the eight D48 findings closed for real (Session 49, D49).

Covers: schema-dispatched verify + score (D49.1), the machine-readable outcome map with a drift
guard against the prose and an explicit `.5` rounding rule (D49.2), the three-way OTS classifier
(D49.3), and the honest question-first counters + conditional banner (D49.6). The single-source
graded-state and proof-chain semantics are exercised by the end-to-end rehearsal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from schelling.backtest.grade import classify_ots_output
from schelling.backtest.mapping import apply_linear_map, map_outcome, round_half_up
from schelling.backtest.scoring import score_record
from schelling.backtest.verify import verify_record
from schelling.report.rubric_lookup import lookup_rubric
from schelling.schemas.forecast import (
    CrowdForecastRecord,
    ForecastRecord,
    LLMForecastRecord,
)
from schelling.schemas.question import LinearMap

_REPO_ROOT = Path(__file__).resolve().parent.parent
_RUNS = _REPO_ROOT / "runs"
_LEDGER = _REPO_ROOT / "FORECASTS.md"

_OPEC_RECORDS = sorted(_RUNS.glob("Q-2026-OPEC-SEP-*.json")) if _RUNS.exists() else []
_needs_runs = pytest.mark.skipif(not _OPEC_RECORDS, reason="runs/ is gitignored — local only")


# ------------------------------------------------------------------ D49.2 machine-readable mapping
def _opec_rubric() -> object:
    looked = lookup_rubric("Q-2026-OPEC-SEP", _REPO_ROOT)
    assert looked is not None, "OPEC grading file must be findable"
    return looked[0]


def _prose_grade(raw: float) -> float:
    """The committed OPEC prose formula, transcribed verbatim: grade = 50 + adjustment/600*50,
    clamped to [0,100], nearest integer with ties up (the declared rounding)."""
    return round_half_up(max(0.0, min(100.0, 50 + raw / 600 * 50)))


@pytest.mark.parametrize(
    "raw",
    [-1200, -600, -401, -400, -18, -6, -1, 0, 1, 6, 18, 188, 300, 599, 600, 601, 1200],
)
def test_opec_outcome_map_matches_prose(raw: float) -> None:
    """The executable ``outcome_map`` reproduces the committed prose formula exactly (D49.2).

    The structured mapping is a verbatim restatement of the prose; a future edit to one that does
    not match the other fails here — exactly as the band-array drift guard does for banded rubrics
    (D24.4). The prose governs on disagreement, and this pins them together.
    """
    rubric = _opec_rubric()
    assert rubric.outcome_map is not None
    value, _ = map_outcome(rubric, float(raw))
    assert value == _prose_grade(float(raw))


def test_opec_map_rounding_half_up_at_the_point_five_boundary() -> None:
    """The declared rounding is nearest-integer, ties UP — pinned at a real ``.5`` boundary (D49.2).

    raw = 6 thousand b/d gives exactly 50.5 on the continuum; the declared ``nearest_int_half_up``
    resolves it to 51, where Python's banker's ``round`` gives 50. The rounding rule is not left
    to a library default.
    """
    rubric = _opec_rubric()
    value, _ = map_outcome(rubric, 6.0)
    assert value == 51.0  # not 50 — banker's rounding would disagree
    assert round(50.5) == 50  # documents the default we are deliberately overriding


def test_round_half_up_ties_go_up() -> None:
    assert round_half_up(50.5) == 51.0
    assert round_half_up(49.5) == 50.0
    assert round_half_up(0.5) == 1.0
    assert round_half_up(50.4999) == 50.0


def test_linear_map_clamps() -> None:
    m = LinearMap(unit="x", slope=1.0, intercept=50.0)
    assert apply_linear_map(m, 100.0) == 100.0  # clamped high
    assert apply_linear_map(m, -100.0) == 0.0  # clamped low


def test_unsupported_rounding_rule_raises() -> None:
    m = LinearMap(unit="x", slope=1.0, intercept=0.0, rounding="banker")
    with pytest.raises(ValueError, match="unsupported rounding"):
        apply_linear_map(m, 1.0)


# ------------------------------------------------------------------ D49.3 three-way OTS classifier
def test_ots_confirmed_does_not_block() -> None:
    status, blocks = classify_ots_output(0, "Success! Bitcoin block 800000 attests existence")
    assert status == "confirmed" and blocks is False


def test_ots_attestation_only_does_not_block() -> None:
    out = (
        "Got 3 attestation(s) from cache\nCould not connect to Bitcoin node: Cookie file unusable\n"
    )
    status, blocks = classify_ots_output(1, out)
    assert status == "attestation_only" and blocks is False


def test_ots_pending_confirmation_does_not_block() -> None:
    """A freshly stamped proof reports 'Pending confirmation in Bitcoin blockchain' — a calendar
    commitment awaiting a Bitcoin block, case (c), not a mismatch (D49.3)."""
    out = (
        "Calendar https://alice.btc.calendar.opentimestamps.org: "
        "Pending confirmation in Bitcoin blockchain\n"
    )
    status, blocks = classify_ots_output(1, out)
    assert status == "attestation_only" and blocks is False


def test_ots_hash_mismatch_blocks() -> None:
    out = "Expected sha256 aaaa but got bbbb — does not match"
    status, blocks = classify_ots_output(1, out)
    assert status == "mismatch" and blocks is True


def test_ots_unrecognised_output_blocks_conservatively() -> None:
    status, blocks = classify_ots_output(2, "some totally unexpected error")
    assert status == "mismatch" and blocks is True


# ------------------------------------------------------------------ D49.1 verify dispatches
@_needs_runs
@pytest.mark.parametrize("record_path", _OPEC_RECORDS, ids=lambda p: p.name)
def test_every_sealed_opec_record_verifies(record_path: Path) -> None:
    """Every sealed OPEC row — solver AND llm-judgment — verifies (D49.1). The pre-D49 hard-coded
    ForecastRecord parse raised on the llm rows; the dispatch fixes that (D48.1)."""
    report = verify_record(record_path, _LEDGER)
    assert report.ok, [f"{c.name}:{c.detail}" for c in report.checks if not c.passed]


# ------------------------------------------------------------------ D49.1 score_record dispatches
def _synthetic_llm(bands_probs: dict[str, float] | None = None) -> LLMForecastRecord:
    from schelling.schemas.forecast import Ensemble, LLMSample

    return LLMForecastRecord(
        question_id="Q-TEST",
        run_id="r",
        engine_version="e",
        inputs_hash="h",
        judge_model="claude-opus-4-8",
        temperature=0.0,
        n_samples=5,
        prompt_hash="p",
        cost_usd=0.0,
        ensemble=Ensemble(median=58.0, mean=58.0, p10=50.0, p90=66.0, n_draws=5),
        band_probabilities=bands_probs or {},
        self_consistency=0.0,
        samples=[LLMSample(point=58.0)],
    )


@_needs_runs
def test_score_record_dispatches_forecast_and_llm() -> None:
    """A ForecastRecord gets abs-error + CRPS; an LLMForecastRecord gets abs-error only on an
    arithmetic rubric — both scoreable, neither crashes (D49.1)."""
    forecast = next(p for p in _OPEC_RECORDS if "mc10000" in p.name and "compromise" not in p.name)
    fc = ForecastRecord.model_validate_json(forecast.read_text())
    card = score_record(fc, 66.0)
    assert card.primary is not None and card.primary.name == "absolute_error"
    assert any(s.name == "crps" for s in card.secondary)

    llm_path = next(p for p in _OPEC_RECORDS if "llm-n5" in p.name)
    llm = LLMForecastRecord.model_validate_json(llm_path.read_text())
    llm_card = score_record(llm, 66.0)
    assert llm_card.primary is not None
    assert abs(llm_card.primary.value - abs(llm.ensemble.median - 66.0)) < 1e-9


def test_score_record_crowd_is_binary_only() -> None:
    """A CrowdForecastRecord is scoreable but carries NO continuum score (D47.2 / D49.1)."""
    from schelling.schemas.forecast import Ensemble

    crowd = CrowdForecastRecord(
        question_id="Q-TEST",
        run_id="r",
        inputs_hash="h",
        metaculus_id=1,
        metaculus_url="https://metaculus.com/q/1",
        match_justification="matched by hand",
        binary_prob_met=0.7,
        ensemble=Ensemble(median=70.0, mean=70.0, p10=60.0, p90=80.0, n_draws=1),
    )
    card = score_record(crowd, 66.0)
    assert card.scores == []  # never a |median - actual| number
    assert "binary track" in card.note.lower()
