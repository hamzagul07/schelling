"""Tests for the paper evidence + figure generators (Session 14): determinism + honest sourcing."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import app
from schelling.paper.assemble import _resolve_tags, assemble, parse_evidence
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


# --------------------------------------------------------------- assembly (Session 15, D15.1)
def test_parse_evidence_reads_the_table() -> None:
    md = "\n".join(
        [
            "| E-tag | Section | Metric | Value | Source | Provenance | Note |",
            "|---|---|---|---|---|---|---|",
            "| E-FOO | S | m | 12.3 | `a.csv` | `abc123` | note |",
        ]
    )
    ev = parse_evidence(md)
    assert ev["E-FOO"] == {"value": "12.3", "source": "a.csv", "prov": "abc123"}


def test_resolve_tag_inline_value_and_provenance_footnote() -> None:
    ev = {"E-FOO": {"value": "12.3", "source": "a.csv", "prov": "abc"}}
    out, used, todos = _resolve_tags("the value is [E-FOO].", ev)
    assert "(12.3)[^ev-E-FOO]" in out and "E-FOO" in used and todos == []


def test_resolve_two_tags_in_one_bracket_keeps_connective() -> None:
    ev = {
        "E-A": {"value": "1", "source": "s", "prov": "p"},
        "E-B": {"value": "2", "source": "s", "prov": "p"},
    }
    out, used, _ = _resolve_tags("[E-A vs E-B]", ev)
    assert "(1 vs 2)[^ev-E-A][^ev-E-B]" in out and set(used) == {"E-A", "E-B"}


def test_resolve_family_prefix_joins_members() -> None:
    ev = {
        "E-LEDGER-x": {"value": "9", "source": "F", "prov": "p"},
        "E-LEDGER-y": {"value": "8", "source": "F", "prov": "p"},
    }
    out, used, _ = _resolve_tags("[E-LEDGER]", ev)
    assert "(9, 8)[^ev-E-LEDGER]" in out and "E-LEDGER" in used


def test_resolve_unknown_tag_is_visible_todo_never_silent() -> None:
    out, used, todos = _resolve_tags("[E-NOPE]", {})
    assert "**TODO(E-NOPE)**" in out and todos == ["E-NOPE"] and used == {}


def test_resolve_suppresses_echo_when_value_already_in_prose() -> None:
    # D16.2: a tag confirming a number already written in the sentence resolves footnote-only.
    ev = {"E-N": {"value": "351", "source": "s", "prov": "p"}}
    out, used, _ = _resolve_tags("comprises 351 scoreable issues [E-N].", ev)
    assert "issues[^ev-E-N]" in out and "(351)" not in out and "E-N" in used


def test_resolve_keeps_echo_when_value_absent_from_prose() -> None:
    ev = {"E-M": {"value": "9.530", "source": "s", "prov": "p"}}
    out, _used, _ = _resolve_tags("reproduces the reference case [E-M].", ev)
    assert "(9.530)[^ev-E-M]" in out  # no prose number -> value echoed


def test_assemble_repo_deterministic_complete_and_consistent() -> None:
    a, todos_a, missing_a = assemble(REPO)
    b, _todos_b, _missing_b = assemble(REPO)
    assert a == b  # deterministic + idempotent
    assert todos_a == [] and missing_a == []  # committed EVIDENCE.md resolves every draft tag
    for heading in ("## Abstract", "## 1. Introduction", "## 2. ", "## 10. Conclusion"):
        assert heading in a  # eleven sections concatenated in order
    assert "figures/fig_deu_error_histogram.svg" in a and "figures/fig_r1_split.svg" in a
    assert "Section 9 limitations. Section 10 concludes." in a  # roadmap fixed (item 5)
    assert "Meehl, P.E. (1954)" in a  # verified bibliography appended
    # duplicate-number suppression (D16.2): E-DEU-N confirms the prose "351" -> footnote-only
    assert "issues[^ev-E-DEU-N]" in a and "(351)[^ev-E-DEU-N]" not in a
    assert "[^ev-E-DEU-N]:" in a  # provenance footnote still defined


def test_paper_assemble_cli_reports_no_unresolved(tmp_path: Path) -> None:
    out = tmp_path / "DRAFT.md"
    result = runner.invoke(app, ["paper-assemble", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists() and "unresolved E-tags: none" in result.output


@pytest.mark.skipif(not DEU_CSV.exists(), reason="DEU III data not present (gitignored)")
def test_round1_and_context_tags_present(tmp_path: Path) -> None:
    result = runner.invoke(app, ["paper-evidence", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    text = (tmp_path / "EVIDENCE.md").read_text()
    assert "| E-DEU-MAE-r1 |" in text and "| 28.31 |" in text  # handicapped round-1 challenge
    assert "| E-BASE-WMEAN-r1 |" in text and "| 23.64 |" in text  # round-1 weighted mean
    assert "| E-CTX-bdm2011 |" in text and "| E-WORST |" in text


# --------------------------------------------------------------- paper-evidence --check (D18.3)
def _bundle(items: list[EvidenceItem]) -> EvidenceBundle:
    return EvidenceBundle(items=items, open_questions=[])  # record=None -> data_absent path


def _mk(tag: str, value: str, prov: str = "abc123") -> EvidenceItem:
    return EvidenceItem(tag, "S", "metric", value, "src", prov, "note")


def test_check_in_sync_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_mk("E-REPL-MEDIAN", "9.530"), _mk("E-TESTS", "279")]
    monkeypatch.setattr("schelling.paper.evidence.build_evidence", lambda repo_root: _bundle(items))
    (tmp_path / "EVIDENCE.md").write_text(evidence_markdown(_bundle(items)))
    r = runner.invoke(app, ["paper-evidence", "--check", "--out-dir", str(tmp_path)])
    assert r.exit_code == 0 and "in sync" in r.output


def test_check_science_drift_fails_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = [_mk("E-REPL-MEDIAN", "9.530")]
    stale = [_mk("E-REPL-MEDIAN", "9.999")]  # committed carries a different science number
    monkeypatch.setattr("schelling.paper.evidence.build_evidence", lambda repo_root: _bundle(fresh))
    (tmp_path / "EVIDENCE.md").write_text(evidence_markdown(_bundle(stale)))
    r = runner.invoke(app, ["paper-evidence", "--check", "--out-dir", str(tmp_path)])
    assert r.exit_code == 1 and "SCIENCE DRIFT" in r.output and "E-REPL-MEDIAN" in r.output


def test_check_provenance_only_drift_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = [_mk("E-REPL-MEDIAN", "9.530", prov="newhash")]
    stale = [_mk("E-REPL-MEDIAN", "9.530", prov="oldhash")]  # same value, different provenance
    monkeypatch.setattr("schelling.paper.evidence.build_evidence", lambda repo_root: _bundle(fresh))
    (tmp_path / "EVIDENCE.md").write_text(evidence_markdown(_bundle(stale)))
    r = runner.invoke(app, ["paper-evidence", "--check", "--out-dir", str(tmp_path)])
    assert r.exit_code == 0 and "provenance" in r.output.lower()


def test_check_test_count_is_not_science(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = [_mk("E-TESTS", "279")]
    stale = [_mk("E-TESTS", "267")]  # 267 -> 279 is a repro stat, not a manuscript science number
    monkeypatch.setattr("schelling.paper.evidence.build_evidence", lambda repo_root: _bundle(fresh))
    (tmp_path / "EVIDENCE.md").write_text(evidence_markdown(_bundle(stale)))
    r = runner.invoke(app, ["paper-evidence", "--check", "--out-dir", str(tmp_path)])
    assert r.exit_code == 0 and "E-TESTS" in r.output


def test_check_without_committed_file_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("schelling.paper.evidence.build_evidence", lambda repo_root: _bundle([]))
    r = runner.invoke(app, ["paper-evidence", "--check", "--out-dir", str(tmp_path)])
    assert r.exit_code == 2 and "no committed" in r.output
