"""Session 12: the SHA-256 seal ledger + tornado zero-swing diagnostics."""

from __future__ import annotations

import hashlib
from pathlib import Path

from typer.testing import CliRunner

from schelling.backtest.ledger import (
    LEDGER_END,
    empty_seal_ledger,
    insert_seal_row,
    record_sha256,
    seal_row,
)
from schelling.cli import app
from schelling.mc.sensitivity import zero_swing_warning
from schelling.schemas.forecast import SensitivityEntry

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "report"


# --------------------------------------------------------------- the SHA-256 seal (D12.0)
def test_record_sha256_matches_openssl_style_file_hash(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text('{"hello": 1}\n')
    assert record_sha256(f) == hashlib.sha256(f.read_bytes()).hexdigest()


def test_insert_seal_row_is_idempotent() -> None:
    doc = empty_seal_ledger("# L")
    row = seal_row(
        model="challenge",
        vintage="v1",
        question_id="Q",
        frozen_at="2026-07-21",
        median=34.576,
        sha="a" * 64,
    )
    once, changed1 = insert_seal_row(doc, row, "a" * 64)
    assert changed1 and "a" * 64 in once and once.count("| challenge |") == 1
    twice, changed2 = insert_seal_row(once, row, "a" * 64)  # same sha again
    assert not changed2 and twice == once  # nothing changes
    assert once.index("| challenge |") < once.index(LEDGER_END)  # row is inside the table


def test_seal_row_format() -> None:
    row = seal_row(
        model="compromise",
        vintage="v2",
        question_id="Q-X",
        frozen_at="2026-07-21",
        median=41.6355,
        sha="b" * 64,
    )
    assert row == f"| compromise | v2 | Q-X | 2026-07-21 | 41.636 | `{'b' * 64}` |"


# --------------------------------------------------------------- the `schelling seal` command
def test_seal_command_appends_then_is_idempotent(tmp_path: Path) -> None:
    record = FIXTURES / "forecast_record.json"
    ledger = tmp_path / "FORECASTS.md"
    sha = record_sha256(record)

    first = runner.invoke(app, ["seal", str(record), "--vintage", "test", "-o", str(ledger)])
    assert first.exit_code == 0, first.output
    assert "Sealed" in first.output and sha in first.output
    text = ledger.read_text()
    assert sha in text and text.count(f"`{sha}`") == 1

    # sealing the same record again changes nothing (idempotent)
    second = runner.invoke(app, ["seal", str(record), "--vintage", "test", "-o", str(ledger)])
    assert second.exit_code == 0
    assert "Already sealed" in second.output
    assert ledger.read_text() == text  # byte-identical, no duplicate row


def test_seal_missing_record_is_friendly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["seal", str(tmp_path / "nope.json")])
    assert result.exit_code == 2
    assert "not found" in result.output
    assert "Traceback" not in result.output


# --------------------------------------------------------------- tornado zero-swing warning (D12.3)
def _entry(param: str, swing: float) -> SensitivityEntry:
    return SensitivityEntry(
        parameter=param,
        actor_id=param.split(".")[0],
        field="salience",
        low_value=0.0,
        high_value=1.0,
        forecast_at_low=0.0,
        forecast_at_high=swing,
        swing=swing,
    )


def test_zero_swing_warning_fires_when_dominated() -> None:
    entries = [_entry(f"a{i}.salience", 0.0) for i in range(18)] + [
        _entry(f"b{i}.salience", 5.0 + i) for i in range(9)
    ]  # 18 of 27 zero — like the v2 challenge run
    warning = zero_swing_warning(entries)
    assert warning is not None
    assert "degenerate median lock" in warning and "18 of 27" in warning


def test_zero_swing_warning_silent_when_healthy() -> None:
    entries = [_entry(f"a{i}.salience", 3.0 + i) for i in range(6)]  # all live
    assert zero_swing_warning(entries) is None
    assert zero_swing_warning([]) is None  # empty table: no warning
