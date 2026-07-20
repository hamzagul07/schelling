"""CLI smoke tests via the typer runner (BUILD_PLAN §8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import app
from schelling.schemas.forecast import ForecastRecord

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
TRANSCRIPTS = Path(__file__).parent.parent / "data" / "transcripts"


def test_solve_reproduces_replication_forecast(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "solve",
            str(FIXTURES / "emission_standards.json"),
            "--draws",
            "100",
            "--seed",
            "42",
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "9.530" in result.output
    # the written record reproduces the deterministic Session-2 forecast (9.53)
    written = next(tmp_path.glob("*.json"))
    record = ForecastRecord.model_validate_json(written.read_text())
    assert record.ensemble.median == pytest.approx(9.53, abs=1e-2)  # exact value 9.52995...
    # zero-variance fixture: every draw identical, so CI80 collapses to the point forecast
    assert record.ensemble.p10 == record.ensemble.p90 == record.ensemble.median


def test_solve_missing_fixture_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["solve", str(tmp_path / "nope.json")])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_knowledge_build_then_search(tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    build = runner.invoke(
        app,
        [
            "knowledge",
            "build",
            "--embedder",
            "hashing",
            "--transcripts",
            str(TRANSCRIPTS),
            "--db",
            str(db),
        ],
    )
    assert build.exit_code == 0, build.output
    assert "indexed" in build.output

    search = runner.invoke(
        app,
        ["knowledge", "search", "the dating game five men five women", "-k", "1", "--db", str(db)],
    )
    assert search.exit_code == 0, search.output
    assert "Game Theory #1: The Dating Game" in search.output


def test_knowledge_search_without_index_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["knowledge", "search", "x", "--db", str(tmp_path / "none.db")])
    assert result.exit_code == 2
    assert "no index" in result.output
