"""CLI smoke tests via the typer runner (BUILD_PLAN §8)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import _startup, app
from schelling.formalizer.client import LLMResult, ReplayClient
from schelling.knowledge.chunker import Chunk
from schelling.knowledge.embed import HashingEmbedder
from schelling.knowledge.index import KnowledgeIndex
from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
TRANSCRIPTS = Path(__file__).parent.parent / "data" / "transcripts"


def _fake_anthropic_factory(text: str) -> Callable[..., ReplayClient]:
    """A drop-in for cli.AnthropicClient that replays a canned completion (no live API)."""

    def make(model: str = "replay-model") -> ReplayClient:
        return ReplayClient([LLMResult(text, 100, 100)], model_name=model)

    return make


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


def test_formalize_writes_draft_and_never_solves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    situation = tmp_path / "situation.txt"
    situation.write_text("Aland, Belland and Cesta negotiate a coal phase-out year.")
    draft_text = (FIXTURES / "formalize_replay.json").read_text()
    monkeypatch.setattr("schelling.cli.AnthropicClient", _fake_anthropic_factory(draft_text))

    out = tmp_path / "draft.json"
    result = runner.invoke(
        app,
        ["formalize", str(situation), "-o", str(out), "--db", str(tmp_path / "none.db")],
    )
    assert result.exit_code == 0, result.output
    # human-readable review output
    assert "Stakeholders" in result.output
    assert "Aland" in result.output
    assert "Open assumptions" in result.output
    assert "DRAFT" in result.output
    # NEVER auto-solves: none of the `solve` command's forecast output appears
    assert "CI80" not in result.output
    assert "Converge:" not in result.output
    assert not list(tmp_path.glob("*mc*.json"))  # no ForecastRecord was written
    # a valid DraftGameSpec was written; its game is solver-ready
    written = out.read_text()
    assert '"question_id": "Q-COAL-PHASEOUT"' in written
    game = GameSpec.model_validate(json.loads(written)["game"])
    assert len(game.actors) == 3


def test_formalize_missing_situation_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["formalize", str(tmp_path / "nope.txt")])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_report_on_replication_fixture_record(tmp_path: Path) -> None:
    # Solve the replication fixture, then render its ForecastRecord to HTML.
    fixture = str(FIXTURES / "emission_standards.json")
    solve = runner.invoke(app, ["solve", fixture, "--draws", "40", "--out-dir", str(tmp_path)])
    assert solve.exit_code == 0, solve.output
    record_path = next(tmp_path.glob("*.json"))

    out = tmp_path / "report.html"
    result = runner.invoke(app, ["report", str(record_path), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "Report written" in result.output
    html = out.read_text()
    assert html.startswith("<!doctype html>")
    assert "Q-1994-EMISSIONS" in html
    for token in ("http://", "https://", "<script", "src="):
        assert token not in html.lower()


def test_report_missing_artifact_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["report", str(tmp_path / "nope.json")])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_report_bad_artifact_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "an artifact"}')
    result = runner.invoke(app, ["report", str(bad)])
    assert result.exit_code == 2
    assert "could not render" in result.output


# --------------------------------------------------------------- env loading (D6.5)
def test_startup_loads_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCHELLING_DOTENV_PROBE", raising=False)
    (tmp_path / ".env").write_text("SCHELLING_DOTENV_PROBE=loaded\n")
    monkeypatch.chdir(tmp_path)
    _startup()
    assert os.environ.get("SCHELLING_DOTENV_PROBE") == "loaded"


def test_formalize_missing_key_is_friendly_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here, so the startup loader finds no key
    situation = tmp_path / "s.txt"
    situation.write_text("Aland, Belland and Cesta negotiate a coal phase-out year.")
    result = runner.invoke(app, ["formalize", str(situation), "--db", str(tmp_path / "none.db")])
    assert result.exit_code == 2
    assert "No ANTHROPIC_API_KEY found" in result.output
    assert "Traceback" not in result.output


def _planted_db(tmp_path: Path, fact: str) -> Path:
    db = tmp_path / "k.db"
    chunk = Chunk(fact, "planted.txt", "Game Theory #99: Planted", 99, 0, 0, len(fact))
    KnowledgeIndex.build([chunk], HashingEmbedder(), db_path=db).close()
    return db


def test_formalize_leak_quarantines_rejected_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fact = "The Zorbian Federation fields nine hundred hypersonic interceptors near its border."
    db = _planted_db(tmp_path, fact)
    leak = json.loads((FIXTURES / "formalize_replay.json").read_text())
    leak["game"]["actors"][0]["evidence"][0]["note"] = (
        "Zorbian Federation fields nine hundred hypersonic interceptors."
    )
    leak_text = json.dumps(leak)
    monkeypatch.setattr(
        "schelling.cli.AnthropicClient",
        lambda model="x": ReplayClient([LLMResult(leak_text, 10, 10)] * 2),
    )
    situation = tmp_path / "s.txt"
    situation.write_text("Aland, Belland and Cesta negotiate a coal phase-out year.")
    out = tmp_path / "draft.json"
    result = runner.invoke(app, ["formalize", str(situation), "-o", str(out), "--db", str(db)])
    assert result.exit_code == 2
    assert "Blocked" in result.output and "quarantined" in result.output
    assert "Traceback" not in result.output
    quarantine = out.with_suffix(".quarantine.json")
    assert quarantine.exists()
    assert "game" in json.loads(quarantine.read_text())  # rejected draft saved for inspection
