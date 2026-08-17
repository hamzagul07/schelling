"""The DEU reviewer data package (Session 60, D60): the per-issue CSV and its summary statistics.

Pins the packaged numbers to a fresh computation from the committed dataset — so the reviewer
package can never drift from the data, and the CSV is reproducible. POST-HOC/exploratory; nothing
sealed is touched (a check asserts the solver default is unchanged). The DEU CSV is gitignored, so
the data-dependent tests skip on CI and run locally.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from schelling.backtest.deu import DEFAULT_CSV
from schelling.backtest.review import (
    load_scored_issues,
    paired_rows,
    residual_r2,
    summary,
    to_csv,
)
from schelling.schemas.backtest import DEUIssue

REPO = Path(__file__).resolve().parent.parent
_Trip = tuple[float, float, float]

pytestmark = pytest.mark.skipif(
    not DEFAULT_CSV.exists(), reason="DEU CSV is gitignored; run locally"
)


@pytest.fixture(scope="module")
def scored() -> tuple[list[DEUIssue], float]:
    return load_scored_issues()


def test_scored_set_is_351_and_q_tuned(scored: tuple[list[DEUIssue], float]) -> None:
    issues, q = scored
    assert len(issues) == 351
    assert q == 0.7


def test_committed_csv_matches_fresh_generation(scored: tuple[list[DEUIssue], float]) -> None:
    """The committed per-issue CSV equals a fresh regeneration (drift guard; no hand-typed cell)."""
    issues, q = scored
    committed = (REPO / "docs" / "review" / "deu-paired-differences.csv").read_text()
    assert committed == to_csv(paired_rows(issues, q))
    assert len(committed.splitlines()) == 352  # header + 351 rows


def test_summary_headline_numbers_match_the_package(scored: tuple[list[DEUIssue], float]) -> None:
    issues, q = scored
    s = summary(issues, q)
    assert s["challenge_mean_ae"] == pytest.approx(26.829, abs=0.01)
    assert s["compromise_mean_ae"] == pytest.approx(22.992, abs=0.01)
    assert s["challenge_median_ae"] == pytest.approx(20.0, abs=0.01)
    assert s["compromise_median_ae"] == pytest.approx(17.544, abs=0.01)
    assert s["mde_paired_mae"] == pytest.approx(3.04, abs=0.02)


def test_loss_function_ranking_flips(scored: tuple[list[DEUIssue], float]) -> None:
    """The package's central claim: the challenge loses on mean AE but wins on tight hit-rates."""
    issues, q = scored
    s = summary(issues, q)
    # §3 headline CI excludes 0 (compromise significantly better on mean AE)
    base, lo, _hi = cast(_Trip, s["mean_ae_diff_ci"])
    assert base > 0 and lo > 0
    # median-AE difference CI INCLUDES 0 (not significant)
    _mbase, mlo, mhi = cast(_Trip, s["median_ae_diff_ci"])
    assert mlo < 0 < mhi
    # challenge wins the tight-hit criteria
    hit = cast("dict[int, tuple[float, float]]", s["hit_rates"])
    assert hit[5][0] > hit[5][1] and hit[10][0] > hit[10][1]
    # CRPS essentially tied
    crps = cast("dict[str, float]", s["crps_weighted_empirical"])
    assert abs(crps["challenge"] - crps["compromise"]) < 1.0


def test_win_counts_and_sign_test(scored: tuple[list[DEUIssue], float]) -> None:
    issues, q = scored
    s = summary(issues, q)
    wins = cast("dict[str, int]", s["wins"])
    assert wins["challenge"] + wins["compromise"] + wins["ties"] == 351
    assert wins["challenge"] == 157 and wins["compromise"] == 194
    assert s["sign_test_p"] == pytest.approx(0.055, abs=0.01)


def test_residual_probe_recovers_no_signal(scored: tuple[list[DEUIssue], float]) -> None:
    """The oracle reframed (D61): CV R^2 on the residual y-wmean is ~0, CI spans 0."""
    issues, _q = scored
    r2, lo, hi = residual_r2(issues)
    assert r2 == pytest.approx(-0.029, abs=0.01)
    assert lo < 0 < hi  # indistinguishable from zero -> no signal beyond the weighted mean


def test_nothing_sealed_changed_solver_default_untouched() -> None:
    """The exploratory sweep monkeypatched in-script; the committed solver default is intact."""
    from schelling.solver.config import SolverConfig

    cfg = SolverConfig()
    assert cfg.security_mode == "adversary" and cfg.q == 1.0 and cfg.apply_risk is True
    assert "proposal_order" not in SolverConfig.model_fields  # no schema change was committed
