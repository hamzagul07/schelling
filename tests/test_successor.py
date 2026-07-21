"""Session R1 tests: the pre-registered split, candidate fitting, the TEST protocol, and shipping.

Offline by construction: split logic uses synthetic ids, candidate fitting uses synthetic rows, and
the committed split/candidate JSONs load without the (gitignored) DEU CSV. The one end-to-end test
that needs the real data is guarded on its presence, so CI stays green without it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.backtest.deu import DEFAULT_CSV
from schelling.backtest.split import (
    SPLIT_SEED,
    load_committed_split,
    make_split,
    split_counts,
)
from schelling.backtest.successor import (
    CandidateResult,
    IssueData,
    SuccessorReport,
    bootstrap_delta_ci,
    compromise_pred,
    fit_candidate_a,
    fit_candidate_b,
    forecast_candidate,
    leaderboard_markdown,
    load_candidate,
    mae,
    predict_for_game,
)
from schelling.schemas.question import GameSpec

FIXTURES = Path(__file__).parent / "fixtures"


def _game(name: str) -> GameSpec:
    return GameSpec.model_validate(json.loads((FIXTURES / name).read_text()))


# --------------------------------------------------------------- the pre-registered split (R1.0)
def test_split_is_deterministic_and_proportioned() -> None:
    ids = [f"issue-{k}" for k in range(1000)]
    a = make_split(ids)
    b = make_split(ids)
    assert a == b  # deterministic
    counts = split_counts(a)
    assert (
        counts["train"] == 400 and counts["dev"] == 300 and counts["test"] == 300
    )  # exact 40/30/30
    # order-independent: shuffling the input does not change any assignment
    assert make_split(list(reversed(ids))) == a


def test_split_seed_changes_partition() -> None:
    ids = [f"issue-{k}" for k in range(300)]
    assert make_split(ids, seed=SPLIT_SEED) != make_split(ids, seed=SPLIT_SEED + 1)


def test_committed_split_loads_and_covers_351() -> None:
    assignment = load_committed_split()
    counts = split_counts(assignment)
    assert sum(counts.values()) == 351
    assert counts == {"train": 140, "dev": 105, "test": 106}
    assert set(assignment.values()) == {"train", "dev", "test"}


# --------------------------------------------------------------- candidate fitting (synthetic rows)
def _rows(n: int, split: str) -> list[IssueData]:
    rows = []
    for k in range(n):
        wmean = 30.0 + (k % 7) * 8.0
        rp = 10.0 + (k % 5) * 15.0
        y = 0.7 * wmean + 0.3 * rp + ((k % 3) - 1) * 2.0  # mostly wmean, some rp, small noise
        rows.append(
            IssueData(
                issue_id=f"{split}-{k}",
                split=split,
                outcome=y,
                wmean=wmean,
                challenge=wmean + 5.0,
                rp=rp,
                rule_cod=float(k % 2),
                gini=0.3 + 0.01 * (k % 10),
                herfindahl=0.2 + 0.01 * (k % 8),
                polarization=0.1 + 0.01 * (k % 6),
                n_actors=5 + (k % 20),
            )
        )
    return rows


def test_candidate_a_fit_is_deterministic() -> None:
    train = _rows(60, "train")
    a1 = fit_candidate_a(train, l2=0.1)
    a2 = fit_candidate_a(train, l2=0.1)
    assert a1.beta == a2.beta and a1.mean == a2.mean  # byte-identical fit (rule 2)
    pred = a1.predict(train)
    assert pred.shape == (60,) and all(0 <= p <= 100 for p in pred)


def test_candidate_b_fit_is_deterministic_and_pi_sums_to_one() -> None:
    train = _rows(60, "train")
    b1 = fit_candidate_b(train, l2=0.1)
    b2 = fit_candidate_b(train, l2=0.1)
    assert b1.weights == b2.weights
    regimes = b1.mean_regime_weights(train)
    assert set(regimes) == {"compromise", "challenge", "status_quo"}
    assert abs(sum(regimes.values()) - 1.0) < 1e-9  # softmax weights are a distribution


# --------------------------------------------------------------- bootstrap + gate logic (R1.3)
def test_bootstrap_delta_ci_is_deterministic_and_ordered() -> None:
    rows = _rows(80, "test")
    # a "candidate" that is just the compromise -> delta ~ 0
    same = compromise_pred(rows)
    point, lo, hi = bootstrap_delta_ci(same, rows, seed=1)
    assert point == pytest.approx(0.0, abs=1e-9)
    assert lo <= point <= hi
    # deterministic under the seed
    assert bootstrap_delta_ci(same, rows, seed=1) == bootstrap_delta_ci(same, rows, seed=1)


def test_gate_uses_sign_of_delta() -> None:
    rows = _rows(50, "test")
    y = [r.outcome for r in rows]
    better = compromise_pred(rows).copy()
    better[:] = y  # a perfect predictor beats compromise
    point, _lo, _hi = bootstrap_delta_ci(better, rows, seed=1)
    assert point < 0.0  # negative delta = beats compromise
    assert mae(better, rows) < mae(compromise_pred(rows), rows)


# --------------------------------------------------------------- shipping as --solver (committed)
def test_committed_candidates_load_and_predict() -> None:
    game = _game("emission_standards.json")
    for kind in ("gravity", "regime"):
        cand = load_candidate(kind)
        value = predict_for_game(cand, game)
        assert 0.0 <= value <= 100.0


def test_forecast_candidate_tags_the_model() -> None:
    game = _game("emission_standards.json")
    rec = forecast_candidate(game, "gravity", n_draws=10, seed=1, write=False)
    assert rec.model == "gravity"
    assert "gravity" in rec.run_id
    assert rec.median_trajectory == []  # candidates carry no round trajectory


# --------------------------------------------------------------- leaderboard rendering
def test_leaderboard_reports_no_survivor() -> None:
    losers = [
        CandidateResult(
            key="regime",
            name="Candidate B",
            applies_to="TEST",
            l2=1.0,
            dev_mae=24.0,
            dev_compromise_mae=23.0,
            n_test=106,
            test_compromise_mae=21.0,
            test_mae=21.5,
            delta=0.5,
            ci_lo=-0.7,
            ci_hi=1.8,
            beats_compromise=False,
        )
    ]
    report = SuccessorReport(
        dataset_sha256="x",
        split_seed=SPLIT_SEED,
        split_counts={"train": 140, "dev": 105, "test": 106},
        boot_seed=1,
        candidates=losers,
        any_survivor=False,
    )
    md = leaderboard_markdown(report)
    assert "No candidate beats the compromise" in md
    assert "nothing was sealed" in md
    assert "TEST scored once" in md


# ----------------------------------------------------------- full pipeline (needs real DEU data)
@pytest.mark.skipif(not DEFAULT_CSV.exists(), reason="DEU CSV is gitignored; run locally")
def test_successor_search_reproduces_test_verdict() -> None:
    from schelling.backtest.successor import run_successor_search

    r1, _a1, _b1 = run_successor_search()
    r2, _a2, _b2 = run_successor_search()
    assert r1 == r2  # deterministic end to end
    assert (
        r1.any_survivor is False
    )  # the pre-registered TEST verdict: no candidate beats compromise
    for c in r1.candidates:
        assert c.beats_compromise == (c.delta < 0.0)
