"""CLI smoke tests via the typer runner (BUILD_PLAN §8)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import _startup, app
from schelling.formalizer.client import LLMResult, ReplayClient, WebSource
from schelling.knowledge.chunker import Chunk
from schelling.knowledge.embed import HashingEmbedder
from schelling.knowledge.index import KnowledgeIndex
from schelling.schemas.forecast import AdviseRecord, ForecastRecord
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
            "--solver",
            "challenge",
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "9.530" in result.output
    # the written record reproduces the deterministic Session-2 forecast (9.53)
    written = next(tmp_path.glob("*.json"))
    record = ForecastRecord.model_validate_json(written.read_text())
    assert record.model == "challenge"
    assert record.ensemble.median == pytest.approx(9.53, abs=1e-2)  # exact value 9.52995...
    # zero-variance fixture: every draw identical, so CI80 collapses to the point forecast
    assert record.ensemble.p10 == record.ensemble.p90 == record.ensemble.median


def test_solve_both_models_writes_two_records(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "solve",
            str(FIXTURES / "emission_standards.json"),
            "--draws",
            "50",
            "--out-dir",
            str(tmp_path),
        ],  # --solver defaults to both
    )
    assert result.exit_code == 0, result.output
    assert "challenge" in result.output and "compromise" in result.output
    models = {
        ForecastRecord.model_validate_json(p.read_text()).model for p in tmp_path.glob("*.json")
    }
    assert models == {"challenge", "compromise"}


def test_solve_missing_fixture_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["solve", str(tmp_path / "nope.json")])
    assert result.exit_code == 2
    assert "not found" in result.output


# --------------------------------------------------------------- solve accepts drafts (D6.8)
def test_solve_on_draft_carries_assumptions_and_provenance(tmp_path: Path) -> None:
    draft = FIXTURES / "report" / "draft.json"  # a DraftGameSpec
    result = runner.invoke(app, ["solve", str(draft), "--draws", "20", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    record = ForecastRecord.model_validate_json(next(tmp_path.glob("*.json")).read_text())
    assert len(record.assumptions) == 2  # carried from the draft
    assert record.formalizer_metadata is not None
    assert record.formalizer_metadata.model == "claude-opus-4-8"


def test_solve_on_bare_gamespec_has_no_draft_provenance(tmp_path: Path) -> None:
    fixture = str(FIXTURES / "emission_standards.json")  # a bare GameSpec
    result = runner.invoke(app, ["solve", fixture, "--draws", "20", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    record = ForecastRecord.model_validate_json(next(tmp_path.glob("*.json")).read_text())
    assert record.assumptions == []
    assert record.formalizer_metadata is None


def test_solve_invalid_json_is_friendly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = runner.invoke(app, ["solve", str(bad), "--out-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "not valid JSON" in result.output
    assert "Traceback" not in result.output


def test_solve_malformed_draft_is_friendly(tmp_path: Path) -> None:
    bad = tmp_path / "d.json"
    bad.write_text(json.dumps({"game": {}, "assumptions": [], "template_classification": {}}))
    result = runner.invoke(app, ["solve", str(bad), "--out-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "DraftGameSpec" in result.output and "formalize" in result.output
    assert "Traceback" not in result.output


def test_solve_bad_gamespec_is_friendly(tmp_path: Path) -> None:
    bad = tmp_path / "g.json"
    bad.write_text(json.dumps({"question_id": "Q", "actors": []}))  # not draft-shaped, invalid game
    result = runner.invoke(app, ["solve", str(bad), "--out-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "GameSpec" in result.output
    assert "Traceback" not in result.output


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


def test_knowledge_build_missing_extra_is_friendly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_name: str) -> object:
        raise ImportError("no sentence_transformers")

    monkeypatch.setattr("schelling.cli.make_embedder", boom)
    result = runner.invoke(
        app,
        [
            "knowledge",
            "build",
            "--embedder",
            "bge-m3",
            "--transcripts",
            str(TRANSCRIPTS),
            "--db",
            str(tmp_path / "k.db"),
        ],
    )
    assert result.exit_code == 2
    assert "knowledge" in result.output.lower() and "uv sync" in result.output
    assert "Traceback" not in result.output


def test_formalize_no_knowledge_skips_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Even with an index present, --no-knowledge formalizes ungrounded (no embedder needed).
    db = tmp_path / "k.db"
    KnowledgeIndex.build(
        [Chunk("x", "p.txt", "Game Theory #9: P", 9, 0, 0, 1)], HashingEmbedder(), db_path=db
    ).close()
    monkeypatch.setattr(
        "schelling.cli.AnthropicClient",
        _fake_anthropic_factory((FIXTURES / "formalize_replay.json").read_text()),
    )
    situation = tmp_path / "s.txt"
    situation.write_text("Aland, Belland and Cesta negotiate a coal phase-out year.")
    result = runner.invoke(
        app,
        [
            "formalize",
            str(situation),
            "-o",
            str(tmp_path / "d.json"),
            "--db",
            str(db),
            "--no-knowledge",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Draft written" in result.output


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


def test_formalize_search_prints_sources_and_marks_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_text = (FIXTURES / "formalize_replay.json").read_text()
    source = WebSource(
        url="https://src.example/aland", title="Aland 2030 target", snippet="2030 phase-out."
    )

    def make(model: str = "replay-model") -> ReplayClient:
        return ReplayClient(
            [LLMResult(draft_text, 100, 100, searches_used=2, sources=(source,))], model_name=model
        )

    monkeypatch.setattr("schelling.cli.AnthropicClient", make)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")  # the live-client key gate
    situation = tmp_path / "s.txt"
    situation.write_text("Aland, Belland and Cesta negotiate a coal phase-out year.")
    out = tmp_path / "d.json"
    result = runner.invoke(
        app,
        ["formalize", str(situation), "-o", str(out), "--db", str(tmp_path / "n.db"), "--search"],
    )
    assert result.exit_code == 0, result.output
    assert "Live-searched" in result.output and "Aland 2030 target" in result.output
    from schelling.formalizer.schemas import DraftGameSpec

    draft = DraftGameSpec.model_validate_json(out.read_text())
    assert draft.live_searched is True
    assert [s.url for s in draft.sources_fetched] == ["https://src.example/aland"]
    assert draft.metadata.searches_used == 2


def test_analyze_no_review_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft_text = (FIXTURES / "formalize_replay.json").read_text()
    monkeypatch.setattr("schelling.cli.AnthropicClient", _fake_anthropic_factory(draft_text))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    result = runner.invoke(
        app,
        [
            "analyze",
            "Aland, Belland and Cesta negotiate a coal phase-out year.",
            "--no-review",
            "--no-knowledge",
            "--draws",
            "30",
            "-o",
            str(tmp_path / "d.json"),
            "--out-dir",
            str(tmp_path),
            "--report",
            str(tmp_path / "r.html"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Draft written" in result.output and "Report:" in result.output
    assert "1. medians:" in result.output
    assert "challenge median" in result.output and "compromise median" in result.output
    assert "4. top lever:" in result.output and "5. assumptions flagged:" in result.output
    assert (tmp_path / "d.json").exists() and (tmp_path / "r.html").exists()
    models = {
        ForecastRecord.model_validate_json(p.read_text()).model for p in tmp_path.glob("*mc*.json")
    }
    assert {"challenge", "compromise"} <= models  # both models solved and written


def test_analyze_review_gate_default_on_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_text = (FIXTURES / "formalize_replay.json").read_text()
    monkeypatch.setattr("schelling.cli.AnthropicClient", _fake_anthropic_factory(draft_text))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    # review is default-on; declining at the prompt stops before solving
    result = runner.invoke(
        app,
        [
            "analyze",
            "Aland Belland Cesta coal.",
            "--no-knowledge",
            "-o",
            str(tmp_path / "d.json"),
            "--out-dir",
            str(tmp_path),
        ],
        input="n\n",
    )
    assert result.exit_code == 0, result.output
    assert "Stopped before solving" in result.output
    assert (tmp_path / "d.json").exists()  # the draft was written
    assert not list(tmp_path.glob("*mc*.json"))  # but nothing was solved


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


def test_backtest_cli_on_sample_writes_md_and_record(tmp_path: Path) -> None:
    md = tmp_path / "BACKTEST.md"
    result = runner.invoke(
        app,
        [
            "backtest",
            str(FIXTURES / "deu_sample.csv"),
            "--seed",
            "7",
            "--draws",
            "40",
            "--md",
            str(md),
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Gate" in result.output  # a verdict is printed
    assert "Compromise" in result.output  # the compromise/weighted-mean method is reported
    assert md.exists() and "DEU benchmark" in md.read_text()
    from schelling.schemas.backtest import BacktestRecord

    written = next(tmp_path.glob("backtest-*.json"))
    rec = BacktestRecord.model_validate_json(written.read_text())
    # CLI defaults to the fair fight: sourced capabilities + rp-anchored primary (Session 10).
    assert rec.n_issues == 3
    assert rec.capability_mode == "sourced"
    assert rec.primary_method == "challenge_rp"
    assert rec.split_sample is not None


def test_backtest_cli_missing_csv_is_friendly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["backtest", str(tmp_path)])  # empty dir, no CSV
    assert result.exit_code == 2
    assert "DEU CSV not found" in result.output
    assert "Traceback" not in result.output


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


# --------------------------------------------------------------- advise (Session 7)
_WIDENED = str(FIXTURES / "emission_standards_widened.json")


def test_advise_writes_records_and_prints_caveat(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "advise",
            _WIDENED,
            "--actor",
            "germany",
            "--draws-per-candidate",
            "20",
            "--target-draws",
            "40",
            "--seed",
            "7",
            "--grid-step",
            "10",
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Top own moves" in result.output and "persuasion targets" in result.output
    assert "One-sided search" in result.output  # standing caveat printed
    advise_files = list(tmp_path.glob("*-advise-*.json"))
    assert len(advise_files) == 1
    record = AdviseRecord.model_validate_json(advise_files[0].read_text())
    assert record.advising_actor == "germany"
    assert (tmp_path / f"{record.baseline_run_id}.json").exists()  # baseline reference written


def test_advise_report_renders(tmp_path: Path) -> None:
    adv = runner.invoke(
        app,
        [
            "advise",
            _WIDENED,
            "--actor",
            "germany",
            "--draws-per-candidate",
            "20",
            "--target-draws",
            "40",
            "--seed",
            "7",
            "--grid-step",
            "10",
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert adv.exit_code == 0, adv.output
    advise_json = next(tmp_path.glob("*-advise-*.json"))
    out = tmp_path / "advise.html"
    result = runner.invoke(app, ["report", str(advise_json), "-o", str(out)])
    assert result.exit_code == 0, result.output
    html = out.read_text()
    assert "One-sided search" in html and "Who to work on" in html


def test_advise_unknown_actor_is_friendly(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["advise", _WIDENED, "--actor", "nobody", "--out-dir", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "not in this game" in result.output
    assert "Traceback" not in result.output


# --------------------------------------------------------------- advise 2.0 strategy (Session 21)
def test_advise_equilibrium_mode_prints_successor_caveat(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "advise",
            _WIDENED,
            "--actor",
            "germany",
            "--solver",
            "compromise",
            "--mode",
            "equilibrium",
            "--draws-per-candidate",
            "20",
            "--target-draws",
            "40",
            "--seed",
            "7",
            "--grid-step",
            "10",
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "upper bound on adaptation" in result.output  # SUCCESSOR_CAVEAT, not the one-sided one
    record = AdviseRecord.model_validate_json(next(tmp_path.glob("*-advise-*.json")).read_text())
    assert record.mode == "equilibrium" and record.equilibrium is not None


def test_advise_equilibrium_needs_the_exact_lens(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "advise",
            _WIDENED,
            "--actor",
            "germany",
            "--solver",
            "challenge",
            "--mode",
            "equilibrium",
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 2
    assert "needs the exact lens" in result.output
    assert "Traceback" not in result.output


def test_advise_rejects_unknown_mode(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["advise", _WIDENED, "--actor", "germany", "--mode", "wander", "--out-dir", str(tmp_path)],
    )
    assert result.exit_code == 2
    assert "--mode must be" in result.output


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
