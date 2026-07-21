"""Tests for the paper evidence + figure generators (Session 14): determinism + honest sourcing."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import app
from schelling.paper.evidence import (
    EvidenceBundle,
    EvidenceItem,
    _ledger_items,
    _replication_items,
    evidence_markdown,
)
from schelling.paper.figures import _histogram, write_figures

runner = CliRunner()
REPO = Path(__file__).parent.parent
DEU_CSV = REPO / "data" / "deu" / "Dataset_DEU_III.csv"


def test_ledger_items_parse_the_committed_forecasts_ledger() -> None:
    items, open_q = _ledger_items(REPO)
    assert open_q == []
    medians = {it.tag: it.value for it in items}
    # the four sealed US-Iran rows, read (not typed) from FORECASTS.md
    assert medians["E-LEDGER-challenge-v1"] == "34.576"
    assert medians["E-LEDGER-compromise-v1"] == "41.636"
    assert medians["E-LEDGER-challenge-v2"] == "29.407"
    assert medians["E-LEDGER-compromise-v2"] == "39.443"
    assert all(it.source == "FORECASTS.md" for it in items)


def test_replication_item_re_solves_the_fixture_to_953() -> None:
    items = _replication_items(REPO)
    by_tag = {it.tag: it for it in items}
    assert by_tag["E-REPL-MEDIAN"].value == "9.530"  # re-derived, not hand-typed
    assert by_tag["E-REPL-CI"].value == "(9.530, 9.530)"  # point fixture -> collapsed CI


def test_histogram_binning_is_deterministic_and_bounded() -> None:
    counts = _histogram([0.0, 5.0, 9.9, 10.0, 99.9, 100.0, 100.0], bins=10, hi=100.0)
    assert sum(counts) == 7
    assert counts[0] == 3  # 0, 5, 9.9
    assert counts[1] == 1  # 10.0
    assert counts[9] == 3  # 99.9 and the two 100.0 clamp into the last bin


def test_evidence_markdown_is_a_pure_table_with_open_questions_section() -> None:
    bundle = EvidenceBundle(
        items=[EvidenceItem("E-X", "S", "metric", "1.23", "a.json", "abc123", "note|with pipe")],
        open_questions=["something unsourced"],
    )
    md = evidence_markdown(bundle)
    assert "| E-tag | Section | Metric | Value | Source | Provenance | Note |" in md
    assert "| E-X | S | metric | 1.23 | `a.json` | `abc123` | note\\|with pipe |" in md
    assert "## Open questions" in md and "- something unsourced" in md


def test_evidence_markdown_reports_no_open_questions_cleanly() -> None:
    md = evidence_markdown(EvidenceBundle(items=[], open_questions=[]))
    assert "(none — every cited number resolved to an artifact)" in md


def _fake_report() -> object:
    from schelling.backtest.successor import CandidateResult, SuccessorReport

    cand = CandidateResult(
        key="gravity",
        name="Candidate A",
        applies_to="TEST rp-issues",
        l2=1.0,
        dev_mae=24.96,
        dev_compromise_mae=23.87,
        n_test=50,
        test_compromise_mae=21.26,
        test_mae=22.09,
        delta=0.83,
        ci_lo=-0.15,
        ci_hi=1.91,
        beats_compromise=False,
    )
    return SuccessorReport(
        dataset_sha256="deadbeef" * 8,
        split_seed=20260721,
        split_counts={"train": 140, "dev": 105, "test": 106},
        boot_seed=20260721,
        candidates=[cand],
        any_survivor=False,
    )


def test_figures_from_report_are_byte_stable(tmp_path: Path) -> None:
    report = _fake_report()
    a = tmp_path / "a"
    b = tmp_path / "b"
    write_figures(a, None, report)  # type: ignore[arg-type]
    write_figures(b, None, report)  # type: ignore[arg-type]
    for name in ("fig_leaderboard.svg", "fig_r1_split.svg"):
        assert (a / name).read_bytes() == (b / name).read_bytes()  # deterministic
        assert (a / name).read_text().startswith("<svg")
    # the R1 split figure carries the pre-registered counts
    assert "140" in (a / "fig_r1_split.svg").read_text()


@pytest.mark.skipif(not DEU_CSV.exists(), reason="DEU III data not present (gitignored)")
def test_paper_evidence_cli_end_to_end_and_deterministic(tmp_path: Path) -> None:
    def run() -> None:
        result = runner.invoke(app, ["paper-evidence", "--out-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output

    run()
    ev1 = (tmp_path / "EVIDENCE.md").read_bytes()
    figs = sorted(p.name for p in (tmp_path / "figures").glob("*.svg"))
    assert figs == [
        "fig_challenge_vs_compromise.svg",
        "fig_deu_error_histogram.svg",
        "fig_leaderboard.svg",
        "fig_r1_split.svg",
    ]
    # a couple of headline numbers, computed from data — must match BACKTEST.md
    text = (tmp_path / "EVIDENCE.md").read_text()
    assert "| 351 |" in text  # DEU issue count
    assert "26.83 / 38.51" in text  # primary challenge MAE/RMSE
    assert "-0.84" in text  # oracle ceiling gap
    assert (
        "every cited number resolved to an artifact" in text
    )  # no open questions with data present
    run()  # regenerate
    assert (tmp_path / "EVIDENCE.md").read_bytes() == ev1  # byte-identical
