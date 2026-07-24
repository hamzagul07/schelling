"""Monte Carlo + ForecastRecord tests (BUILD_PLAN §6; §3 audit artifact)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from schelling.mc.monte_carlo import (
    build_forecast_record,
    ci80,
    convergence_stats,
    forecast,
    inputs_hash,
    run_monte_carlo,
)
from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.expected_utility import eu_matrix, expected_utility
from schelling.solver.model import run

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def widened_game() -> GameSpec:
    return GameSpec.model_validate(
        json.loads((FIXTURES / "emission_standards_widened.json").read_text())
    )


@pytest.fixture
def replication_game() -> GameSpec:
    return GameSpec.model_validate(json.loads((FIXTURES / "emission_standards.json").read_text()))


# --------------------------------------------------------------- vectorization parity
def test_eu_matrix_vectorized_matches_scalar() -> None:
    x = np.array([4.0, 7.0, 10.0, 5.0, 9.0, 4.0])
    sal = np.array([80.0, 40.0, 90.0, 20.0, 60.0, 100.0])
    cs = np.array([0.5, 0.3, 0.9, 0.1, 0.6, 0.2])
    r = np.array([1.0, 0.7, 2.0, 1.4, 0.9, 1.1])
    m = eu_matrix(x, sal, cs, mu=7.0, cont_range=6.0, r=r, q=1.0)
    for i in range(x.size):
        for j in range(x.size):
            if i == j:
                assert m[i, j] == 0.0
            else:
                expected = expected_utility(i, j, x, sal, cs, 7.0, 6.0, float(r[i]), 1.0)
                assert m[i, j] == pytest.approx(expected, abs=1e-12)


# --------------------------------------------------------------- (a) reproducibility
def test_reproducible_same_seed_byte_identical(widened_game: GameSpec) -> None:
    cfg = SolverConfig()
    a = forecast(widened_game, cfg, n_draws=300, seed=42, write=False)
    b = forecast(widened_game, cfg, n_draws=300, seed=42, write=False)
    assert a.model_dump_json() == b.model_dump_json()


def test_different_seed_changes_distribution(widened_game: GameSpec) -> None:
    cfg = SolverConfig()
    a = forecast(widened_game, cfg, n_draws=300, seed=1, write=False)
    b = forecast(widened_game, cfg, n_draws=300, seed=2, write=False)
    assert a.outcome_distribution != b.outcome_distribution


# --------------------------------------------------------------- (b) zero variance
def test_zero_variance_on_point_fixture(replication_game: GameSpec) -> None:
    cfg = SolverConfig()
    deterministic = run(replication_game, cfg).forecast_median
    mc = run_monte_carlo(replication_game, cfg, n_draws=200, seed=3)
    assert np.all(mc.median_distribution == deterministic)

    record = build_forecast_record(replication_game, cfg, mc, sensitivity=[])
    assert record.ensemble.median == pytest.approx(deterministic)
    assert (record.ensemble.p10, record.ensemble.p90) == (deterministic, deterministic)
    assert record.ensemble.n_draws == 200
    assert set(record.outcome_distribution) == {deterministic}


# --------------------------------------------------------------- (c) non-degenerate
def test_widened_fixture_is_non_degenerate(widened_game: GameSpec) -> None:
    cfg = SolverConfig()
    record = forecast(widened_game, cfg, n_draws=1000, seed=11, write=False)
    dist = record.outcome_distribution
    assert len(set(dist)) > 50  # a real spread, not a spike
    assert record.ensemble.p10 < record.ensemble.median < record.ensemble.p90
    # a sensible tornado is attached
    assert {e.parameter for e in record.sensitivity} == {"france.position", "germany.position"}
    assert abs(record.sensitivity[0].swing) > 0.0


# --------------------------------------------------------------- record emission / IO
def test_forecast_writes_record_to_runs(widened_game: GameSpec, tmp_path: Path) -> None:
    record = forecast(widened_game, n_draws=100, seed=0, out_dir=tmp_path)
    written = tmp_path / f"{record.run_id}.json"
    assert written.exists()
    reloaded = ForecastRecord.model_validate_json(written.read_text())
    assert reloaded == record
    # engine version recorded: the integer solver version (D39) plus the git SHA for provenance
    assert record.engine_version == 1
    assert record.engine_sha
    assert record.solver_config["q"] == 1.0


def test_inputs_hash_depends_on_game_and_config(
    widened_game: GameSpec, replication_game: GameSpec
) -> None:
    cfg = SolverConfig()
    other = SolverConfig(q=0.5)
    assert inputs_hash(widened_game, cfg) != inputs_hash(replication_game, cfg)
    assert inputs_hash(widened_game, cfg) != inputs_hash(widened_game, other)
    assert inputs_hash(widened_game, cfg) == inputs_hash(widened_game, SolverConfig())


def test_ci80_and_convergence_stats() -> None:
    dist = np.arange(0.0, 100.0)  # 0..99
    low, high = ci80(dist)
    assert low == pytest.approx(np.percentile(dist, 10))
    assert high == pytest.approx(np.percentile(dist, 90))


def test_convergence_stats_report_rates(replication_game: GameSpec) -> None:
    mc = run_monte_carlo(replication_game, SolverConfig(), n_draws=50, seed=0)
    stats = convergence_stats(mc)
    assert stats["n_draws"] == 50.0
    assert stats["converged_fraction"] + stats["round_cap_fraction"] <= 1.0
    assert stats["rounds_min"] <= stats["rounds_mean"] <= stats["rounds_max"]


# --------------------------------------------------------------- (d) performance
def test_ten_thousand_draws_under_sixty_seconds(widened_game: GameSpec) -> None:
    start = time.perf_counter()
    mc = run_monte_carlo(widened_game, SolverConfig(), n_draws=10_000, seed=0)
    elapsed = time.perf_counter() - start
    assert mc.n_draws == 10_000
    assert elapsed < 60.0, f"10k draws took {elapsed:.1f}s (budget 60s)"
