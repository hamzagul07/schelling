"""Engine versioning (Session 39, D39): the solver registry, verify re-solving under the record's
declared engine version, PASS-with-note when a version is retired, legacy migration, and — the
permanent regression gate — every sealed record verifying under the engine it was sealed with."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from schelling.backtest.verify import verify_record
from schelling.mc.monte_carlo import forecast, write_record
from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec
from schelling.solver.registry import CURRENT_ENGINE_VERSION, ENGINE_REGISTRY, resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def _emission_game() -> GameSpec:
    return GameSpec.model_validate_json((FIXTURES / "emission_standards.json").read_text())


# --------------------------------------------------------------------------- registry (D39.1)
def test_registry_has_v1_and_current_is_1() -> None:
    assert CURRENT_ENGINE_VERSION == 1
    assert 1 in ENGINE_REGISTRY
    assert resolve(1) is not None
    assert resolve(999) is None  # a version this build no longer ships


def test_new_records_declare_the_current_engine_version() -> None:
    rec = forecast(_emission_game(), n_draws=20, seed=1, write=False)
    assert rec.engine_version == CURRENT_ENGINE_VERSION == 1
    assert rec.engine_sha  # git SHA still recorded, separately


def test_legacy_engine_version_string_migrates() -> None:
    """A pre-D39 record stored the git SHA in a string ``engine_version``; it must still load, with
    the SHA moved to ``engine_sha`` and the integer version defaulting to 1 (D39.1)."""
    rec = ForecastRecord.model_validate(
        {
            "question_id": "Q",
            "run_id": "r",
            "engine_version": "deadbeef" * 5,  # legacy: a git SHA
            "inputs_hash": "h",
            "seed": 42,
            "ensemble": {"median": 50, "mean": 50, "p10": 40, "p90": 60, "n_draws": 10},
        }
    )
    assert rec.engine_version == 1
    assert rec.engine_sha == "deadbeef" * 5


# ------------------------------------------------------------------- verify dispatch (D39.1/3)
def _sealed_at(tmp_path: Path, record: ForecastRecord) -> tuple[Path, Path]:
    """Write a record and a tiny ledger that seals it; return (record_path, ledger_path)."""
    path = write_record(record, tmp_path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text(f"| challenge | v1 | Q | 2026 | 9.5 | `{sha}` |\n")
    return path, ledger


def test_verify_resolves_under_the_records_engine_version(tmp_path: Path) -> None:
    rec = forecast(_emission_game(), n_draws=100, seed=42, write=False)
    path, ledger = _sealed_at(tmp_path, rec)
    report = verify_record(path, ledger)
    assert report.ok
    determinism = next(c for c in report.checks if c.name == "determinism")
    assert determinism.passed and "engine v1" in determinism.detail


def test_retired_engine_version_is_pass_with_note_not_fail(tmp_path: Path) -> None:
    """A record sealed under an engine this build no longer ships verifies PASS-with-note on
    determinism (hash + ledger still match), never FAIL (D39.3)."""
    rec = forecast(_emission_game(), n_draws=50, seed=7, write=False)
    retired = rec.model_copy(update={"engine_version": 999})
    path, ledger = _sealed_at(tmp_path, retired)
    report = verify_record(path, ledger)
    determinism = next(c for c in report.checks if c.name == "determinism")
    assert determinism.passed  # PASS-with-note, not FAIL
    assert "not re-derivable" in determinism.detail and "999" in determinism.detail
    assert report.ok  # ledger-match + inputs-hash + PASS-with-note determinism


# ----------------------------------------------- THE PERMANENT REGRESSION GATE (D39.2) -----------
def test_all_sealed_records_verify_under_their_engine() -> None:
    """Every sealed solver record re-solves 3/3 through the engine version it was sealed under.

    This is the permanent regression gate for the whole engine expansion: any future change that
    would alter a v1 numerical path fails here. The sealed record files live in gitignored
    ``runs/``, so the gate runs wherever they are present (locally) and skips on CI, like the other
    data-gated tests."""
    runs = REPO_ROOT / "runs"
    ledger = REPO_ROOT / "FORECASTS.md"
    if not runs.exists() or not ledger.exists():
        pytest.skip("runs/ or FORECASTS.md absent (records are gitignored)")
    ledger_text = ledger.read_text()
    checked = 0
    for path in sorted(runs.glob("*.json")):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha not in ledger_text:
            continue  # not a sealed record
        try:
            ForecastRecord.model_validate_json(path.read_text())  # solver records only
        except Exception:
            continue  # an llm-judgment record — verified by its SHA commitment, not re-solved
        report = verify_record(path, ledger)
        assert report.ok, (
            f"{path.name} failed to verify: {[(c.name, c.detail) for c in report.checks]}"
        )
        checked += 1
    assert checked >= 8, f"expected the sealed solver records to be present, found {checked}"
