"""Tests for the tornado sensitivity (BUILD_PLAN §6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.mc.sensitivity import format_tornado, qre_tornado, tornado
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def widened_game() -> GameSpec:
    data = json.loads((FIXTURES / "emission_standards_widened.json").read_text())
    return GameSpec.model_validate(data)


@pytest.fixture
def replication_game() -> GameSpec:
    data = json.loads((FIXTURES / "emission_standards.json").read_text())
    return GameSpec.model_validate(data)


def test_point_estimate_fixture_has_empty_tornado(replication_game: GameSpec) -> None:
    # Every field is a point estimate -> no ranged parameters -> nothing to rank.
    assert tornado(replication_game) == []
    assert "point estimate" in format_tornado([])


def test_qre_tornado_ranges_the_same_params_deterministically(
    widened_game: GameSpec, replication_game: GameSpec
) -> None:
    # The QRE tornado (D42) sweeps the same ranged params as the challenge tornado, deterministic.
    a = qre_tornado(widened_game)
    b = qre_tornado(widened_game)
    assert {e.parameter for e in a} == {"france.position", "germany.position"}
    assert [e.swing for e in a] == [e.swing for e in b]
    # a point-estimate game has no ranged params under QRE either
    assert qre_tornado(replication_game) == []


def test_widened_tornado_ranks_the_widened_positions(widened_game: GameSpec) -> None:
    entries = tornado(widened_game)
    # Only France and Germany positions were widened; those are the only ranged params.
    assert {e.parameter for e in entries} == {"france.position", "germany.position"}
    # Ranked by absolute swing, descending.
    swings = [abs(e.swing) for e in entries]
    assert swings == sorted(swings, reverse=True)
    # Germany's position (widened 2-7) is the dominant lever here.
    assert entries[0].parameter == "germany.position"
    assert abs(entries[0].swing) > 0.0


def test_tornado_entries_carry_low_high_and_forecasts(widened_game: GameSpec) -> None:
    entry = tornado(widened_game)[0]
    assert entry.low_value < entry.high_value
    assert entry.swing == pytest.approx(entry.forecast_at_high - entry.forecast_at_low)


def test_tornado_is_deterministic(widened_game: GameSpec) -> None:
    cfg = SolverConfig()
    a = [e.model_dump() for e in tornado(widened_game, cfg)]
    b = [e.model_dump() for e in tornado(widened_game, cfg)]
    assert a == b
