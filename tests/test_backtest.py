"""DEU backtest tests: ingest round-trip, error math by hand, harness determinism, gate logic.

All offline: uses a tiny committed DEU-format fixture (``deu_sample.csv``); the real dataset lives
under the gitignored ``data/deu/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.backtest.deu import load_deu_issues
from schelling.backtest.harness import (
    median_position_forecast,
    run_backtest,
    weighted_mean_forecast,
)
from schelling.schemas.backtest import BacktestRecord, DEUIssue

SAMPLE = Path(__file__).parent / "fixtures" / "deu_sample.csv"


def _issues() -> list[DEUIssue]:
    return load_deu_issues(SAMPLE)


def _by_id(issues: list[DEUIssue]) -> dict[str, DEUIssue]:
    return {i.issue_id: i for i in issues}


# ------------------------------------------------------------------ ingest + round-trip
def test_ingest_parses_and_filters_invalid_issues() -> None:
    issues = _issues()
    # Two rows are dropped: outcome sentinel 999 (t02i2) and a <3-actor row (t03i1).
    assert [i.issue_id for i in issues] == ["t01i1", "t01i2", "t02i1"]
    a = _by_id(issues)["t01i1"]
    assert len(a.game.actors) == 5
    assert a.outcome == 50.0
    assert all(act.capability.mode == 100.0 for act in a.game.actors)  # equal capability (D9.2)
    assert a.game.actors[0].name == "European Commission"


def test_ingest_round_trips_through_json() -> None:
    for issue in _issues():
        again = DEUIssue.model_validate(json.loads(issue.model_dump_json()))
        assert again == issue


# ------------------------------------------------------------------ error math BY HAND (3 issues)
def test_baseline_forecasts_match_hand_computation() -> None:
    issues = _by_id(_issues())
    # t01i1: pos [80,60,40,20,0], sal [100,50,50,100,50], cap=100 -> weighted by salience.
    #   wmean = (100*80+50*60+50*40+100*20+50*0)/(100+50+50+100+50) = 15000/350 = 42.857142...
    #   median of sorted [0,20,40,60,80] = 40
    assert weighted_mean_forecast(issues["t01i1"].game) == pytest.approx(15000 / 350)
    assert median_position_forecast(issues["t01i1"].game) == 40.0
    # t01i2: pos [100,50,0], equal salience -> plain mean 50; median 50
    assert weighted_mean_forecast(issues["t01i2"].game) == pytest.approx(50.0)
    assert median_position_forecast(issues["t01i2"].game) == 50.0
    # t02i1: pos [0,100,50,50], sal [20,80,50,50] -> wmean = 13000/200 = 65; median (50+50)/2 = 50
    assert weighted_mean_forecast(issues["t02i1"].game) == pytest.approx(65.0)
    assert median_position_forecast(issues["t02i1"].game) == 50.0


def test_mae_aggregation_matches_hand_computation() -> None:
    record = run_backtest(_issues(), csv_path=SAMPLE, dataset_label="sample", seed=7, draws=40)
    methods = {m.key: m for m in record.methods}
    # Weighted-mean errors: |42.857-50|, |50-40|, |65-80| = 7.142857, 10, 15 -> MAE 10.714285...
    wmean_mae = (abs(15000 / 350 - 50) + abs(50 - 40) + abs(65 - 80)) / 3
    assert methods["baseline_wmean"].mae == pytest.approx(wmean_mae)
    # Median errors: |40-50|, |50-40|, |50-80| = 10, 10, 30 -> MAE 50/3
    assert methods["baseline_median"].mae == pytest.approx(50 / 3)
    assert methods["baseline_median"].max_error == 30.0


# ------------------------------------------------------------------ determinism + gate logic
def test_harness_is_deterministic() -> None:
    a = run_backtest(_issues(), csv_path=SAMPLE, dataset_label="s", seed=7, draws=40)
    b = run_backtest(_issues(), csv_path=SAMPLE, dataset_label="s", seed=7, draws=40)
    assert a.model_dump_json() == b.model_dump_json()


def test_gate_passes_iff_primary_beats_both_baselines() -> None:
    record = run_backtest(_issues(), csv_path=SAMPLE, dataset_label="s", seed=7, draws=40)
    mae = {m.key: m.mae for m in record.methods}
    expected = all(mae[record.primary_method] < mae[b] for b in record.baseline_methods)
    assert record.gate_passed == expected
    assert record.primary_method == "solver_paper"
    assert record.baseline_methods == ["baseline_wmean", "baseline_median"]


def test_worst_issues_ranked_by_primary_error() -> None:
    record = run_backtest(_issues(), csv_path=SAMPLE, dataset_label="s", seed=7, draws=40)
    errors = [w.error for w in record.worst_issues]
    assert errors == sorted(errors, reverse=True)  # worst first
    for w in record.worst_issues:
        assert w.error == pytest.approx(abs(w.forecast - w.actual), abs=1e-9)


def test_empty_issue_set_raises() -> None:
    with pytest.raises(ValueError, match="no issues"):
        run_backtest([], csv_path=SAMPLE, dataset_label="s")


def test_dataset_sha256_pins_the_file() -> None:
    record = run_backtest(_issues(), csv_path=SAMPLE, dataset_label="s", seed=7, draws=40)
    assert len(record.dataset_sha256) == 64  # a real SHA-256, pinning the exact CSV
    assert isinstance(BacktestRecord.model_validate_json(record.model_dump_json()), BacktestRecord)
