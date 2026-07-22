"""The LLM judgment baseline (Session 27): sampling, record shape, seal, ranking, contamination.

The LLM is replayed (ReplayClient) so CI never calls the live API. The live sealed ledger is
never touched — the seal test writes to a temp ledger.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import app
from schelling.formalizer.client import LLMResult, ReplayClient
from schelling.llm_forecast.compare import MIN_GRADED, compare_baselines
from schelling.llm_forecast.forecast import (
    LLMForecastError,
    detect_contamination,
    llm_forecast,
    parse_sample,
)
from schelling.schemas.forecast import LLMForecastRecord
from schelling.schemas.question import GameSpec

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _game() -> GameSpec:
    data = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    return GameSpec.model_validate(data["game"])


def _labels() -> list[str]:
    r = _game().resolution_rubric
    assert r is not None
    return [b.label for b in r.bands]


def _resp(point: float, p10: float = 20, p90: float = 50) -> LLMResult:
    labels = _labels()
    bands = ", ".join(f'"{lbl}": {round(1 / len(labels), 4)}' for lbl in labels)
    text = f'{{"point": {point}, "p10": {p10}, "p90": {p90}, "bands": {{{bands}}}}}'
    return LLMResult(text, 100, 50)


def _client(points: list[float]) -> ReplayClient:
    return ReplayClient([_resp(p) for p in points])


# ------------------------------------------------------------- sampling + record shape (items 1,2)
def test_sampling_aggregates_median_and_spread() -> None:
    rec = llm_forecast(_client([30, 35, 28, 40, 33]), _game(), n_samples=5, temperature=1.0)
    assert rec.model == "llm-judgment"  # ledger family label
    assert rec.judge_model == "replay-model" and rec.temperature == 1.0
    assert len(rec.samples) == 5
    assert rec.ensemble.median == 33.0  # median of the sampled points, the headline
    assert rec.ensemble.n_draws == 5
    assert rec.self_consistency == 12.0  # spread = max(40) - min(28)
    assert abs(sum(rec.band_probabilities.values()) - 1.0) < 1e-9  # normalised


def test_record_carries_full_provenance_and_is_sealable_shaped() -> None:
    rec = llm_forecast(
        _client([30, 35, 28, 40, 33]), _game(), n_samples=5, temperature=0.7, engine_version="dead"
    )
    assert len(rec.prompt_hash) == 64 and len(rec.inputs_hash) == 64
    # structurally seal-compatible: ensemble.median (headline), model label, embedded game + rubric
    assert rec.game is not None and rec.game.resolution_rubric is not None
    # round-trips through the schema
    assert LLMForecastRecord.model_validate_json(rec.model_dump_json()) == rec


def test_parse_sample_rejects_unparseable() -> None:
    ok = parse_sample('{"point": 40, "p10": 30, "p90": 55}', [])
    assert ok.point == 40 and ok.p10 == 30 and ok.p90 == 55
    with pytest.raises(LLMForecastError):
        parse_sample("no json here", [])
    with pytest.raises(LLMForecastError):
        parse_sample('{"p10": 30, "p90": 55}', [])  # missing point


# --------------------------------------------------------------- contamination (item 5)
def test_contamination_flagging() -> None:
    game = _game()
    flagged, note = detect_contamination(Path("data/deu/issue.json"), game)
    assert flagged and "CONTAMINATION-RISK" in note
    flagged2, _ = detect_contamination(Path("data/coercive-cases/x.json"), game)
    assert flagged2
    clean, note3 = detect_contamination(Path("analyses/iaea/situation.json"), game)
    assert not clean and note3 == ""


def test_contamination_override_and_autodetect() -> None:
    rec = llm_forecast(
        _client([30, 35, 28, 40, 33]), _game(), n_samples=5, source_path=Path("data/deu/x.json")
    )
    assert rec.contamination_risk is True  # auto-detected from the DEU path
    rec2 = llm_forecast(
        _client([30, 35, 28, 40, 33]),
        _game(),
        n_samples=5,
        source_path=Path("data/deu/x.json"),
        contamination_override=False,
    )
    assert rec2.contamination_risk is False  # caller forced --live-question


# --------------------------------------------------------------- refuse-to-rank guard (item 4)
def _ledger_and_grades(n: int) -> tuple[str, dict[str, float]]:
    rows, grades = [], {}
    for i in range(n):
        q = f"Q-{i}"
        rows += [
            f"| challenge | v1 | {q} | 2026 | {30 + i}.0 | h |",
            f"| compromise | v1 | {q} | 2026 | {40 + i}.0 | h |",
            f"| llm-judgment | v1 | {q} | 2026 | {35 + i}.0 | h |",
        ]
        grades[q] = 32.0 + i
    return "\n".join(rows), grades


def test_compare_refuses_ranking_before_threshold() -> None:
    ledger, grades = _ledger_and_grades(MIN_GRADED - 1)
    result = compare_baselines(ledger, grades)
    assert result.ready is False and result.scores == []  # no ranking
    assert f"{MIN_GRADED - 1}/{MIN_GRADED}" in result.note and "Exploratory" in result.note


def test_compare_ranks_at_threshold() -> None:
    ledger, grades = _ledger_and_grades(MIN_GRADED)
    result = compare_baselines(ledger, grades)
    assert result.ready is True
    assert {s.family for s in result.scores} == {"challenge", "compromise", "llm-judgment"}
    assert result.scores == sorted(result.scores, key=lambda s: s.mae)  # ranked best-first


def test_compare_needs_all_three_families() -> None:
    # A question with only two families sealed does not count toward the graded threshold.
    ledger = (
        "| challenge | v1 | Q-A | 2026 | 30.0 | h |\n| compromise | v1 | Q-A | 2026 | 40.0 | h |"
    )
    result = compare_baselines(ledger, {"Q-A": 32.0})
    assert result.graded_count == 0 and result.ready is False


# --------------------------------------------------------------- seal path (item 3) + render
def test_seal_accepts_an_llm_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rec = llm_forecast(_client([30, 35, 28, 40, 33]), _game(), n_samples=5, engine_version="dead")
    rec_path = tmp_path / "llm.json"
    rec_path.write_text(rec.model_dump_json(indent=2) + "\n")
    ledger = tmp_path / "ledger.md"
    monkeypatch.setattr("schelling.cli.stamp_ledger", lambda *a, **k: (None, "skipped"))
    result = runner.invoke(
        app,
        [
            "seal",
            str(rec_path),
            "--vintage",
            "v1",
            "--out",
            str(ledger),
            "--proofs-dir",
            str(tmp_path / "proofs"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "| llm-judgment | v1 |" in ledger.read_text()  # labelled llm-judgment (item 3)


def test_render_states_non_determinism() -> None:
    from schelling.report.render import render

    rec = llm_forecast(_client([30, 35, 28, 40, 33]), _game(), n_samples=5)
    html = render(json.loads(rec.model_dump_json()))
    assert "LLM judgment baseline" in html
    assert "non-deterministic" in html and "model judgment, not a computed forecast" in html


# --------------------------------------------------------------- CLI (replayed, no live API)
def test_cli_llm_forecast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    game_path = tmp_path / "game.json"
    game_path.write_text(_game().model_dump_json())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(
        "schelling.cli.AnthropicClient", lambda model="m": _client([30, 35, 28, 40, 33])
    )
    result = runner.invoke(
        app, ["llm-forecast", str(game_path), "--samples", "5", "--out-dir", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "headline (median of 5 samples): 33.0" in result.output
    assert "Non-deterministic" in result.output
    rec_files = list(tmp_path.glob("*-llm-*.json"))
    assert len(rec_files) == 1
