"""Session 17 — integrity hardening: resolution rubric, verify, external anchoring."""

from __future__ import annotations

import json
from pathlib import Path

import subprocess

import pytest
from typer.testing import CliRunner

from schelling.backtest.ledger import record_sha256, stamp_ledger
from schelling.backtest.verify import verify_record
from schelling.cli import app
from schelling.mc.monte_carlo import forecast, inputs_hash
from schelling.schemas.question import GameSpec, ResolutionRubric
from schelling.solver.config import SolverConfig

runner = CliRunner()
FIX = Path(__file__).parent / "fixtures"

_RUBRIC = ResolutionRubric(
    resolution_criteria="did the event occur by the deadline (binary)",
    adjudicating_sources=["official statements", "wire services of record"],
    outcome_mapping="map the settlement onto 0-100 by anchor bands",
    grading_formula="score = |forecast_median - actual| on the 0-100 continuum",
)


def _game(with_rubric: bool = False) -> GameSpec:
    game = GameSpec.model_validate_json((FIX / "emission_standards.json").read_text())
    return game.model_copy(update={"resolution_rubric": _RUBRIC}) if with_rubric else game


def _sealed_record(
    tmp_path: Path, *, in_ledger: bool = True, tamper: bool = False
) -> tuple[Path, Path]:
    rec = forecast(_game(with_rubric=True), SolverConfig(), n_draws=100, seed=42, write=False)
    data = json.loads(rec.model_dump_json())
    if tamper:
        data["ensemble"]["median"] = data["ensemble"]["median"] + 5.0
    rpath = tmp_path / "rec.json"
    rpath.write_text(json.dumps(data, indent=2) + "\n")
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text(f"| x | `{record_sha256(rpath)}` |\n" if in_ledger else "no seals here\n")
    return rpath, ledger


# --------------------------------------------------------------- resolution rubric (D17.1)
def test_resolution_rubric_is_excluded_from_inputs_hash() -> None:
    # a grading rubric is metadata, not a solver input: it must not change the content-address,
    # which also keeps records sealed before the rubric existed byte-stable.
    assert inputs_hash(_game(False), SolverConfig()) == inputs_hash(_game(True), SolverConfig())


def test_rubric_does_not_change_the_forecast() -> None:
    a = forecast(_game(False), SolverConfig(), n_draws=100, seed=42, write=False)
    b = forecast(_game(True), SolverConfig(), n_draws=100, seed=42, write=False)
    assert a.ensemble.median == b.ensemble.median and a.inputs_hash == b.inputs_hash


# --------------------------------------------------------------- verify (D17.3)
def test_verify_passes_on_a_freshly_sealed_record(tmp_path: Path) -> None:
    rpath, ledger = _sealed_record(tmp_path)
    report = verify_record(rpath, ledger)
    assert report.ok
    assert {c.name for c in report.checks} == {"ledger-match", "inputs-hash", "determinism"}


def test_verify_fails_when_hash_absent_from_ledger(tmp_path: Path) -> None:
    rpath, ledger = _sealed_record(tmp_path, in_ledger=False)
    report = verify_record(rpath, ledger)
    assert not report.ok
    assert not next(c for c in report.checks if c.name == "ledger-match").passed


def test_verify_catches_a_tampered_forecast(tmp_path: Path) -> None:
    # the tampered bytes are sealed (ledger-match passes) but re-solving exposes the edit.
    rpath, ledger = _sealed_record(tmp_path, tamper=True)
    report = verify_record(rpath, ledger)
    assert next(c for c in report.checks if c.name == "ledger-match").passed
    assert not next(c for c in report.checks if c.name == "determinism").passed
    assert not report.ok


def test_verify_cli_reports_pass_per_check(tmp_path: Path) -> None:
    rpath, ledger = _sealed_record(tmp_path)
    result = runner.invoke(app, ["verify", str(rpath), "--ledger", str(ledger)])
    assert result.exit_code == 0, result.output
    assert "VERIFIED" in result.output and result.output.count("[PASS]") == 3


def test_verify_cli_exits_nonzero_on_failure(tmp_path: Path) -> None:
    rpath, ledger = _sealed_record(tmp_path, in_ledger=False)
    result = runner.invoke(app, ["verify", str(rpath), "--ledger", str(ledger)])
    assert result.exit_code == 1
    assert "[FAIL] ledger-match" in result.output and "FAILED" in result.output


# --------------------------------------------------------------- external anchoring (D17.2)
def test_stamp_ledger_is_a_soft_noop_when_ots_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _absent(*_a: object, **_k: object) -> object:
        raise FileNotFoundError("ots")

    monkeypatch.setattr("schelling.backtest.ledger.subprocess.run", _absent)
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text("ledger content\n")
    proof, message = stamp_ledger(ledger, tmp_path / "proofs")
    assert proof is None and "OpenTimestamps" in message  # graceful, never raises


def test_stamp_ledger_stores_and_is_idempotent_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_ots(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        Path(cmd[2] + ".ots").write_bytes(b"fake-proof")  # `ots stamp <file>` writes <file>.ots
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("schelling.backtest.ledger.subprocess.run", _fake_ots)
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text("ledger content\n")
    proofs = tmp_path / "proofs"

    proof, _msg = stamp_ledger(ledger, proofs)
    assert proof is not None and Path(proof).exists() and Path(proof).parent == proofs
    assert not (tmp_path / "FORECASTS.md.ots").exists()  # moved into proofs/, not left beside ledger

    again, msg2 = stamp_ledger(ledger, proofs)  # same ledger bytes -> idempotent
    assert again == proof and "already timestamped" in msg2
