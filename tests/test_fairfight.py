"""Session-10 'fair fight' tests: sourced capabilities, the rp variant, the compromise model,
the split-sample gate, and the forecast ledger. All offline (tiny committed DEU fixture)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.backtest.capability import capabilities_for_issue, regime_for_year
from schelling.backtest.deu import load_deu_issues
from schelling.backtest.harness import run_backtest, weighted_mean_forecast
from schelling.backtest.ledger import forecast_commitment, ledger_entry
from schelling.mc.monte_carlo import forecast
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "deu_sample.csv"


def _game(name: str) -> GameSpec:
    return GameSpec.model_validate(json.loads((FIXTURES / name).read_text()))


# --------------------------------------------------------------- capability sourcing (D10.1-D10.3)
def test_regime_mapping_by_year() -> None:
    assert regime_for_year(2000) == "pre_nice"
    assert regime_for_year(2007) == "nice"
    assert regime_for_year(2018) == "lisbon"


def test_sourced_capabilities_normalize_and_treat_institutions_as_top() -> None:
    caps = capabilities_for_issue(["com", "ep", "de", "mt"], 2007)  # Nice regime
    assert caps["de"] == 100.0  # Germany is the strongest state -> 100
    assert caps["com"] == 100.0 and caps["ep"] == 100.0  # institutions get the largest-state weight
    assert caps["mt"] < 20.0  # Malta (3 votes) is tiny relative to Germany (29)
    # deterministic
    assert caps == capabilities_for_issue(["com", "ep", "de", "mt"], 2007)


def test_capability_module_self_checks_hold() -> None:
    # Importing the module runs the sum assertions; re-check them explicitly here.
    from schelling.backtest.capability import NICE_WEIGHTS, PRE_NICE_WEIGHTS

    assert sum(PRE_NICE_WEIGHTS.values()) == 87
    assert sum(w for c, w in NICE_WEIGHTS.items() if c != "cr") == 345


def test_load_sourced_capability_assigns_treaty_power() -> None:
    equal = load_deu_issues(SAMPLE)
    sourced = load_deu_issues(SAMPLE, sourced_capability=True)
    a_eq = {a.id: a.capability.mode for a in equal[0].game.actors}
    a_src = {a.id: a.capability.mode for a in sourced[0].game.actors}
    assert all(v == 100.0 for v in a_eq.values())  # equal mode: everyone 100
    # sourced mode: the big states (DE/FR/IT, all 29 Nice votes) and the institutions top out at 100
    assert a_src["de"] == 100.0 and a_src["com"] == 100.0
    # a mixed issue genuinely varies (Germany 29 vs Malta 3 in the Nice regime)
    mixed = capabilities_for_issue(["de", "mt", "com"], 2011)
    assert mixed["de"] == 100.0 and mixed["mt"] < 20.0


# --------------------------------------------------------------- reference point (D10.4)
def test_reference_point_changes_forecast() -> None:
    game = _game("emission_standards_widened.json")
    base = run(game, SolverConfig(q=0.5)).forecast_median
    anchored = run(game, SolverConfig(q=0.5, reference_point=2.0)).forecast_median
    assert base != anchored  # the status-quo reference moves the challenge dynamics


def test_reference_point_none_is_unchanged() -> None:
    # rp=None must reproduce the replication forecast exactly (backward compatible).
    game = _game("emission_standards.json")
    assert run(game, SolverConfig()).forecast_median == pytest.approx(9.53, abs=1e-2)
    a = run(game, SolverConfig(q=0.7)).forecast_median
    b = run(game, SolverConfig(q=0.7, reference_point=None)).forecast_median
    assert a == b


# --------------------------------------------------------------- compromise model (D10.5)
def test_compromise_forecast_equals_weighted_mean_on_point_game() -> None:
    game = _game("emission_standards.json")
    rec = forecast(game, n_draws=20, seed=1, write=False, model="compromise")
    assert rec.model == "compromise"
    assert "compromise" in rec.run_id
    assert rec.ensemble.median == pytest.approx(weighted_mean_forecast(game))
    assert rec.median_trajectory == []  # the compromise mean has no round trajectory


def test_challenge_model_is_the_default() -> None:
    rec = forecast(_game("emission_standards.json"), n_draws=20, seed=1, write=False)
    assert rec.model == "challenge"


# --------------------------------------------------------------- the fair-fight gate (item 4)
def test_fair_fight_adds_rp_primary_and_split_sample() -> None:
    issues = load_deu_issues(SAMPLE, sourced_capability=True)
    rec = run_backtest(
        issues,
        csv_path=SAMPLE,
        dataset_label="s",
        seed=7,
        draws=40,
        capability=0.0,
        capability_mode="sourced",
        reference_point=True,
    )
    assert rec.capability_mode == "sourced"
    assert rec.reference_point_used is True
    assert rec.primary_method == "challenge_rp"
    assert any(m.key == "challenge_rp" for m in rec.methods)
    s = rec.split_sample
    assert s is not None
    assert s.train_n + s.test_n == rec.n_issues
    assert s.selected in s.candidates
    assert s.passed == (s.test_mae < s.test_baseline_mae)


def test_fair_fight_is_deterministic() -> None:
    def go() -> str:
        issues = load_deu_issues(SAMPLE, sourced_capability=True)
        return run_backtest(
            issues,
            csv_path=SAMPLE,
            dataset_label="s",
            seed=7,
            draws=40,
            capability=0.0,
            capability_mode="sourced",
            reference_point=True,
        ).model_dump_json()

    assert go() == go()


# --------------------------------------------------------------- forecast ledger (D10.6)
def test_forecast_commitment_is_engine_independent() -> None:
    game = _game("emission_standards.json")
    rec = forecast(game, n_draws=20, seed=1, write=False, model="compromise")
    other = rec.model_copy(update={"engine_sha": "f" * 40, "created_at": "2099-01-01"})
    # the commitment hashes the prediction, not the engine SHA or timestamp.
    assert forecast_commitment(rec) == forecast_commitment(other)
    # a different model gives a different commitment.
    ch = forecast(game, n_draws=20, seed=1, write=False, model="challenge")
    assert forecast_commitment(ch) != forecast_commitment(rec)


def test_ledger_entry_records_both_models() -> None:
    game = _game("emission_standards.json")
    recs = [
        forecast(game, n_draws=20, seed=1, write=False, model=m)
        for m in ("challenge", "compromise")
    ]
    entry = ledger_entry(recs, continuum="test", grade_date="2026-09-01", note="n")
    assert "challenge" in entry and "compromise" in entry
    assert "2026-09-01" in entry
    for r in recs:
        assert forecast_commitment(r)[:16] in entry
