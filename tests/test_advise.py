"""Tests for advise mode (Session 7): determinism, traceability, benefit/cost separation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.advise.search import advise
from schelling.schemas.question import GameSpec

FIXTURES = Path(__file__).parent / "fixtures"


def _game(name: str) -> GameSpec:
    return GameSpec.model_validate(json.loads((FIXTURES / name).read_text()))


def _advise_widened(**kw: object) -> object:
    defaults: dict[str, object] = {
        "draws_per_candidate": 30,
        "target_draws": 60,
        "seed": 42,
        "grid_step": 10.0,
    }
    defaults.update(kw)
    record, _baseline = advise(_game("emission_standards_widened.json"), "germany", **defaults)  # type: ignore[arg-type]
    return record


def test_advise_is_deterministic() -> None:
    a = _advise_widened()
    b = _advise_widened()
    assert a.model_dump_json() == b.model_dump_json()  # type: ignore[attr-defined]


def test_advise_zero_variance_on_point_fixture() -> None:
    record, _ = advise(
        _game("emission_standards.json"), "germany", draws_per_candidate=50, target_draws=50, seed=1
    )
    # point fixture -> zero variance -> baseline equals the Session-2 deterministic forecast
    assert record.baseline_median == pytest.approx(9.53, abs=1e-2)
    again, _ = advise(
        _game("emission_standards.json"), "germany", draws_per_candidate=50, target_draws=50, seed=1
    )
    assert record.model_dump_json() == again.model_dump_json()


def test_advise_traceability_before_and_after() -> None:
    a = _advise_widened()
    assert a.top_moves and a.persuasion_targets  # type: ignore[attr-defined]
    # Every recommended own-move's benefit is exactly |before-ideal| - |after-ideal|.
    for mv in a.top_moves:  # type: ignore[attr-defined]
        expected = abs(a.baseline_median - a.ideal) - abs(mv.settlement_median - a.ideal)  # type: ignore[attr-defined]
        assert mv.benefit == pytest.approx(expected, abs=1e-9)
    for t in a.persuasion_targets:  # type: ignore[attr-defined]
        assert isinstance(t.settlement_median, float)  # 'after' median present on every target


def test_advise_benefit_and_cost_are_separate() -> None:
    a = _advise_widened()
    salience = [m for m in a.own_moves if m.dimension == "salience"]  # type: ignore[attr-defined]
    position = [m for m in a.own_moves if m.dimension == "position"]  # type: ignore[attr-defined]
    assert salience and all(m.cost == 0.0 for m in salience)  # salience moves are cost-free
    assert any(m.cost > 0.0 for m in position)  # conceding position off the ideal costs


def test_advise_flags_moves_beyond_stated_range() -> None:
    a = _advise_widened()
    # Germany's salience is a point estimate (80), so any other salience is beyond its range.
    assert any(m.beyond_stated_range for m in a.own_moves)  # type: ignore[attr-defined]


def test_advise_persuasion_targets_ranked_by_benefit() -> None:
    a = _advise_widened()
    benefits = [t.benefit for t in a.persuasion_targets]  # type: ignore[attr-defined]
    assert benefits == sorted(benefits, reverse=True)


def test_advise_unknown_actor_raises() -> None:
    game = _game("emission_standards_widened.json")
    with pytest.raises(ValueError, match="not in this game"):
        advise(game, "atlantis", draws_per_candidate=10, target_draws=10)


# --------------------------------------------------------------- D8.0 refinements
def test_advise_adaptive_grid_gives_about_twenty_position_points() -> None:
    # grid_step=None -> position step = realized span / 20, so ~21 position candidates regardless
    # of the continuum's units (here the year-scale widened fixture).
    record, _ = advise(
        _game("emission_standards_widened.json"),
        "germany",
        draws_per_candidate=20,
        target_draws=20,
        seed=1,
    )
    positions = [m for m in record.own_moves if m.dimension == "position"]
    assert 20 <= len(positions) <= 22
    # the effective step is recorded in advise_config (not the literal None)
    assert isinstance(record.advise_config["grid_step"], float)
    assert record.advise_config["salience_step"] == 5.0


def test_advise_explicit_grid_step_overrides_adaptive() -> None:
    a, _ = advise(
        _game("emission_standards_widened.json"),
        "germany",
        draws_per_candidate=20,
        target_draws=20,
        seed=1,
        grid_step=10.0,
    )
    assert a.advise_config["grid_step"] == 10.0
    assert a.advise_config["salience_step"] == 10.0  # explicit step applies to both sweeps


def test_advise_persuasion_targets_labeled_energize_or_defuse() -> None:
    record = _advise_widened()
    for t in record.persuasion_targets:  # type: ignore[attr-defined]
        assert t.kind in ("energize", "defuse")
        if t.dimension == "position":
            assert t.kind == "energize"  # pulling a position toward the ideal always energizes
        else:  # salience: raising energizes, lowering defuses
            assert t.kind == ("energize" if t.to_value >= t.from_value else "defuse")
