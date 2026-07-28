"""Honest counters, conditional banner, and single-source graded state (Session 49, D49.5/D49.6).

These need no ``runs/`` — they construct SiteData directly and exercise the graded-state write path
in a tmp repo, so they run in CI.
"""

from __future__ import annotations

from pathlib import Path

from schelling.site.data import LedgerRow, QuestionInfo, SiteData


def _data(graded: frozenset[str]) -> SiteData:
    """Three questions, two records each (six rows); ``graded`` names the graded questions."""
    ledger = [
        LedgerRow(
            model="challenge",
            vintage="v1",
            question=q,
            frozen_at="2026-07-24",
            median="60.0",
            sha256="a" * 64,
        )
        for q in ("Q-A", "Q-B", "Q-C")
    ] + [
        LedgerRow(
            model="compromise",
            vintage="v1",
            question=q,
            frozen_at="2026-07-24",
            median="61.0",
            sha256="b" * 64,
        )
        for q in ("Q-A", "Q-B", "Q-C")
    ]
    questions = {
        q: QuestionInfo(question_id=q, rubric_file=f"GRADING-{q}.md", resolution_date="2026-08-05")
        for q in ("Q-A", "Q-B", "Q-C")
    }
    return SiteData(
        ledger=ledger, questions=questions, graded_questions=graded, grading_date="2026-08-06"
    )


def test_counter_leads_with_questions_not_records() -> None:
    """Headline is questions-first; one graded question of six records never reads as six."""
    d = _data(frozenset({"Q-A"}))
    assert d.graded_questions_count == 1
    assert d.graded_count == 2  # two records of the one graded question
    assert d.graded_counter == "1 of 3 questions graded · 2 of 6 records scored"


def test_banner_zero_graded_claims_nothing() -> None:
    d = _data(frozenset())
    banner = d.honesty_banner()
    assert "Nothing here has been graded yet" in banner
    assert "no accuracy is claimed" in banner


def test_banner_above_zero_below_threshold_names_the_guard() -> None:
    """Above zero, below threshold: state the count, claim no accuracy, name the guard (D49.6)."""
    d = _data(frozenset({"Q-A"}))
    banner = d.honesty_banner()
    assert "1 question graded" in banner
    assert "requires 10 graded questions" in banner
    # never the zero-state sentence on the same page
    assert "Nothing here has been graded yet" not in banner


def test_banner_pluralises() -> None:
    d = _data(frozenset({"Q-A", "Q-B"}))
    assert "2 questions graded" in d.honesty_banner()


def test_graded_state_is_single_sourced(tmp_path: Path) -> None:
    """write_grade leaves BOTH files carrying the outcome, and the site's graded detector — which
    reads the grading file — agrees with the ledger's grade block (D49.5). One notion of graded."""
    from schelling.backtest.grade import GradeReport, OtsResult, write_grade
    from schelling.site.data import _graded_questions

    ledger = tmp_path / "FORECASTS.md"
    ledger.write_text("# ledger\n\n<!-- LEDGER:START -->\n<!-- LEDGER:END -->\n")
    grading = tmp_path / "GRADING-Q-2026-OPEC-SEP.md"
    grading.write_text("# GRADING — Q-2026-OPEC-SEP\n\nrubric prose.\n")

    report = GradeReport(
        question_id="Q-2026-OPEC-SEP",
        actual_raw=188.0,
        actual_continuum=66.0,
        mapping_note="mapped",
        justification="announced +188 kb/d",
        citations=["https://opec.org"],
        rubric_source="GRADING-Q-2026-OPEC-SEP.md",
        ots=OtsResult("attestation_only", False, "calendar attestation retrieved"),
        grades=[],
    )
    write_grade(report, ledger, grading)

    # The grading file carries the Actual-outcome line the site keys on ...
    assert "Q-2026-OPEC-SEP" in _graded_questions(tmp_path)
    # ... and the ledger carries the matching grade block. The two never disagree.
    assert "GRADED — Q-2026-OPEC-SEP" in ledger.read_text()
    assert "Actual outcome" in grading.read_text()
