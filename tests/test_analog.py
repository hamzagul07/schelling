"""ICB analog layer + noise-floor oracle tests (Session 11). Offline via committed data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.analog.icb import ICBAnalogIndex, load_analogs, to_panel
from schelling.backtest.deu import DEFAULT_CSV, load_deu_issues
from schelling.backtest.oracle import oracle_features
from schelling.schemas.forecast import AnalogPanel

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "deu_sample.csv"


# --------------------------------------------------------------- ICB analog layer (D11.2)
def test_committed_analog_table_loads() -> None:
    analogs = load_analogs()
    assert len(analogs) > 1000  # ICB v16 has 1,131 crisis-actors
    a = analogs[0]
    assert a.outcome in ("victory", "compromise", "stalemate", "defeat", "other")


def test_analog_search_is_deterministic_and_distribution_normalized() -> None:
    idx = ICBAnalogIndex.load()
    r1 = idx.search(gravity=6, violence=3, n_actors=8, k=30)
    r2 = idx.search(gravity=6, violence=3, n_actors=8, k=30)
    assert [e.crisno for e in r1.examples] == [e.crisno for e in r2.examples]  # deterministic
    assert r1.n == 30
    assert abs(sum(r1.outcome_distribution.values()) - 1.0) < 1e-9  # a distribution
    assert all(0.0 <= v <= 1.0 for v in r1.outcome_distribution.values())


def test_analog_search_respects_tags() -> None:
    idx = ICBAnalogIndex.load()
    # low-gravity, non-violent vs high-gravity, warlike should retrieve different neighbours
    calm = idx.search(gravity=1, violence=1, n_actors=2, k=20)
    grave = idx.search(gravity=7, violence=4, n_actors=20, k=20)
    assert {e.crisno for e in calm.examples} != {e.crisno for e in grave.examples}


def test_to_panel_discloses_zero_blend_weight() -> None:
    r = ICBAnalogIndex.load().search(gravity=5, violence=2, n_actors=5, k=25)
    panel = to_panel(r)
    assert isinstance(panel, AnalogPanel)
    assert panel.blend_weight == 0.0  # base rate is NOT blended into the solver line
    assert panel.n == 25 and "ICB" in panel.source


# --------------------------------------------------------------- noise-floor oracle (D11.0)
def test_oracle_features_shape_and_positions_included() -> None:
    issues = load_deu_issues(SAMPLE, sourced_capability=True)
    f = oracle_features(issues[0])
    assert f.shape == (18,)  # rich feature vector (positions summarized + structural + rp)
    # min/max positions are included (positions in the features)
    game = issues[0].game
    positions = [a.position.mode for a in game.actors]
    assert min(positions) in f and max(positions) in f


@pytest.mark.skipif(not DEFAULT_CSV.exists(), reason="DEU CSV is gitignored; run locally")
def test_oracle_mean_is_at_the_ceiling() -> None:
    from schelling.backtest.oracle import oracle_summary

    issues = load_deu_issues(DEFAULT_CSV, sourced_capability=True)
    o1 = oracle_summary(issues)
    o2 = oracle_summary(issues)
    assert o1 == o2  # deterministic
    # the headline D11.0 finding: a flexible CV model does not beat the mean (gap <= 0, small)
    assert o1.gap <= 1.0
    assert o1.oracle_mae > 0 and o1.compromise_mae > 0


def test_analog_json_is_committed_package_data() -> None:
    # the compact table ships with the package (like the DEU split), so the layer works offline
    data = json.loads((Path("src/schelling/analog/icb_analogs.json")).read_text())
    assert data["n_records"] == len(data["records"]) > 1000
    assert "ICB" in data["source"]
