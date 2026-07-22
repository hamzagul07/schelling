"""Session 17 — integrity hardening: resolution rubric, verify, external anchoring."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
    assert not (
        tmp_path / "FORECASTS.md.ots"
    ).exists()  # moved into proofs/, not left beside ledger

    again, msg2 = stamp_ledger(ledger, proofs)  # same ledger bytes -> idempotent
    assert again == proof and "already timestamped" in msg2


# --------------------------------------------------------------- epoch-aware hashing (D18.1)
def test_inputs_hash_v1_drops_reference_point_v2_keeps_it() -> None:
    from schelling.mc.monte_carlo import inputs_hash

    game, cfg = _game(), SolverConfig()
    v1 = inputs_hash(game, cfg, hash_version="v1")
    v2 = inputs_hash(game, cfg, hash_version="v2")
    assert v1 != v2  # the reference-point field is the only difference between the epochs
    assert inputs_hash(game, cfg) == v2  # v2 is the current default


def test_inputs_hash_unknown_version_raises() -> None:
    import pytest as _pytest

    from schelling.mc.monte_carlo import inputs_hash

    with _pytest.raises(ValueError, match="unknown hash_version"):
        inputs_hash(_game(), SolverConfig(), hash_version="v3")


def _rewrite(rec_path: Path, **changes: object) -> None:
    data = json.loads(rec_path.read_text())
    for k, v in changes.items():
        if k == "drop_reference_point":
            data["solver_config"].pop("reference_point", None)
        else:
            data[k] = v
    rec_path.write_text(json.dumps(data, indent=2) + "\n")


def test_verify_reproduces_a_v1_era_record_as_pass_with_note(tmp_path: Path) -> None:
    from schelling.mc.monte_carlo import forecast, inputs_hash

    game = _game()
    rec = forecast(game, SolverConfig(), n_draws=100, seed=42, write=False)
    rpath = tmp_path / "v1.json"
    rpath.write_text(rec.model_dump_json(indent=2) + "\n")
    # simulate a record sealed in the pre-reference-point epoch
    _rewrite(
        rpath,
        drop_reference_point=True,
        inputs_hash=inputs_hash(game, SolverConfig(), hash_version="v1"),
    )
    ledger = tmp_path / "L.md"
    ledger.write_text(f"`{record_sha256(rpath)}`\n")
    report = verify_record(rpath, ledger)
    assert report.ok  # 3/3 — verified
    note = next(c for c in report.checks if c.name == "inputs-hash")
    assert note.passed and "legacy v1" in note.detail


def test_verify_tolerates_an_unknown_canonicalization(tmp_path: Path) -> None:
    # Regression (D18.1): a future canonicalization change must never re-break a sealed record —
    # ledger-match + determinism authenticate it even when no known hash epoch reproduces the label.
    from schelling.mc.monte_carlo import forecast

    rec = forecast(_game(), SolverConfig(), n_draws=100, seed=42, write=False)
    rpath = tmp_path / "future.json"
    rpath.write_text(rec.model_dump_json(indent=2) + "\n")
    _rewrite(rpath, inputs_hash="f" * 64)  # a hash from no epoch we recognize
    ledger = tmp_path / "L.md"
    ledger.write_text(f"`{record_sha256(rpath)}`\n")
    report = verify_record(rpath, ledger)
    assert report.ok  # still verified — not re-broken
    note = next(c for c in report.checks if c.name == "inputs-hash")
    assert note.passed and "authenticated by determinism + ledger-match" in note.detail


_SEALED = [
    "runs/Q-2026-USIRAN-STAGE2-mc10000-s42-45d931c6cd91.json",
    "runs/Q-2026-USIRAN-STAGE2-compromise-mc10000-s42-2cbb0bc624f3.json",
    "runs/Q-2026-USIRAN-STAGE2-mc10000-s42-d4441652019a.json",
    "runs/Q-2026-USIRAN-STAGE2-compromise-mc10000-s42-d4441652019a.json",
]


@pytest.mark.skipif(
    not all((Path(__file__).parent.parent / p).exists() for p in _SEALED),
    reason="sealed US-Iran records not present (runs/ is gitignored)",
)
def test_all_four_sealed_records_verify_four_of_four() -> None:
    repo = Path(__file__).parent.parent
    ledger = repo / "FORECASTS.md"
    for p in _SEALED:
        report = verify_record(repo / p, ledger)
        assert report.ok, (
            f"{p} did not verify: {[(c.name, c.passed, c.detail) for c in report.checks]}"
        )


# --------------------------------------------------------------- `schelling stamp` (D18.0)
def test_stamp_command_writes_a_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ots(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        Path(cmd[2] + ".ots").write_bytes(b"proof")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("schelling.backtest.ledger.subprocess.run", _fake_ots)
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text("ledger\n")
    proofs = tmp_path / "proofs"
    result = runner.invoke(app, ["stamp", "--ledger", str(ledger), "--proofs-dir", str(proofs)])
    assert result.exit_code == 0, result.output
    assert list(proofs.glob("*.ots")) and "timestamped" in result.output


def test_stamp_missing_ledger_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["stamp", "--ledger", str(tmp_path / "nope.md")])
    assert result.exit_code == 2 and "not found" in result.output


def test_stamp_exits_nonzero_when_ots_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _absent(*_a: object, **_k: object) -> object:
        raise FileNotFoundError("ots")

    monkeypatch.setattr("schelling.backtest.ledger.subprocess.run", _absent)
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text("ledger\n")
    result = runner.invoke(
        app, ["stamp", "--ledger", str(ledger), "--proofs-dir", str(tmp_path / "p")]
    )
    assert result.exit_code == 1 and "OpenTimestamps" in result.output


# ----------------------------------------------------------- BACKTEST.md section ownership (D18.4)
def test_preserve_leaderboard_keeps_the_successor_block() -> None:
    from schelling.cli import _LEADERBOARD_END, _LEADERBOARD_START, _preserve_leaderboard

    existing = f"old backtest body\n\n{_LEADERBOARD_START}\nLEADER ROWS\n{_LEADERBOARD_END}\n"
    out = _preserve_leaderboard("fresh backtest body", existing)
    assert "fresh backtest body" in out and "LEADER ROWS" in out
    assert _LEADERBOARD_START in out and _LEADERBOARD_END in out


def test_preserve_leaderboard_noop_without_a_block() -> None:
    from schelling.cli import _preserve_leaderboard

    assert _preserve_leaderboard("fresh body", "old body with no markers") == "fresh body"


def test_verify_current_record_reports_v2_epoch(tmp_path: Path) -> None:
    rpath, ledger = _sealed_record(tmp_path)  # a freshly-solved (current-epoch) record
    report = verify_record(rpath, ledger)
    assert report.ok
    assert "(v2)" in next(c for c in report.checks if c.name == "inputs-hash").detail


def test_stamp_second_call_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ots(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        Path(cmd[2] + ".ots").write_bytes(b"proof")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("schelling.backtest.ledger.subprocess.run", _fake_ots)
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text("ledger\n")
    args = ["stamp", "--ledger", str(ledger), "--proofs-dir", str(tmp_path / "proofs")]
    assert runner.invoke(app, args).exit_code == 0
    second = runner.invoke(app, args)  # same bytes -> content-addressed proof already exists
    assert second.exit_code == 0 and "already timestamped" in second.output


_DEU_CSV = Path(__file__).parent.parent / "data" / "deu" / "Dataset_DEU_III.csv"


@pytest.mark.skipif(not _DEU_CSV.exists(), reason="DEU III data not present (gitignored)")
def test_backtest_preserves_existing_leaderboard(tmp_path: Path) -> None:
    from schelling.cli import _LEADERBOARD_END, _LEADERBOARD_START

    md = tmp_path / "BACKTEST.md"
    md.write_text(f"old body\n\n{_LEADERBOARD_START}\nLEADER ROWS\n{_LEADERBOARD_END}\n")
    result = runner.invoke(
        app, ["backtest", "data/deu/", "--draws", "30", "--md", str(md), "--out-dir", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    text = md.read_text()
    assert "LEADER ROWS" in text  # the successor block survived a `backtest` run (D18.4)
    assert "Per-method error" in text  # and the backtest body was refreshed
