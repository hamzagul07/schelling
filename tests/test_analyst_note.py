"""The pre-resolution analyst note for Q-2026-USIRAN-STAGE2 (Session 58, D58).

Pins the note's two tables to the sealed ledger medians and the committed rubric bands — so the note
cannot drift from the records it reads, and no figure in it is hand-typed.
"""

from __future__ import annotations

from pathlib import Path

from schelling.report.analyst_note import (
    outcome_table,
    plausible_bands,
    render_note_tables,
    sealed_medians,
    sourcing_table,
)

REPO = Path(__file__).resolve().parent.parent
QID = "Q-2026-USIRAN-STAGE2"
_FORECASTS = (REPO / "FORECASTS.md").read_text()
_GRADING = (REPO / f"GRADING-{QID}.md").read_text()


def test_plausible_bands_and_midpoints() -> None:
    """The four plausible bands are the middle four, with (lo+hi)/2 midpoints."""
    bands = plausible_bands(_GRADING)
    assert [b.name for b in bands] == ["Collapse", "US terms", "Balanced", "Iranian-leaning"]
    assert [b.midpoint for b in bands] == [20.5, 37.5, 52.5, 65.0]


def _by_band(table: str) -> dict[str, str]:
    """{band-name: last-column} over a table's data rows (skips header + separator)."""
    out: dict[str, str] = {}
    for ln in table.splitlines():
        if not ln.startswith("| ") or "err" in ln or "Graded" in ln:
            continue
        name = ln.split(" (", 1)[0].strip("| ").strip()
        out[name] = ln.rsplit("|", 2)[1].strip()
    return out


def test_outcome_table_winner_flips_across_the_range() -> None:
    """Table (a): challenge is closest only if talks collapse; compromise everywhere else."""
    medians = sealed_medians(_FORECASTS, QID)
    winners = _by_band(outcome_table(medians, plausible_bands(_GRADING)))
    assert winners == {
        "Collapse": "challenge v2",
        "US terms": "compromise v2",
        "Balanced": "compromise v1",
        "Iranian-leaning": "compromise v1",
    }


def test_sourcing_conditional_replicates_only_at_the_low_end() -> None:
    """Table (b): v2-beats-v1 REPLICATES in collapse, SPLITs in US-terms, FAILS in the two higher
    bands — the conditional the note is on record for."""
    medians = sealed_medians(_FORECASTS, QID)
    verdicts = _by_band(sourcing_table(medians, plausible_bands(_GRADING)))
    assert verdicts == {
        "Collapse": "REPLICATES",
        "US terms": "SPLIT",
        "Balanced": "FAILS",
        "Iranian-leaning": "FAILS",
    }


def test_committed_note_matches_the_computation() -> None:
    """Drift guard: the committed GRADING file embeds exactly what the helper computes from the
    ledger and rubric — so no figure in the note is hand-typed or stale (D58)."""
    computed = render_note_tables(_FORECASTS, _GRADING, QID)
    assert computed in _GRADING, "the committed analyst-note tables differ from a fresh computation"


def test_note_changes_no_grading_rule_or_sealed_value() -> None:
    """The note is clearly marked non-authoritative and adds no 'Actual outcome' line (ungraded)."""
    assert "changes NO grading rule and no sealed value" in _GRADING
    assert "Actual outcome" not in _GRADING  # the question is not resolved/graded
