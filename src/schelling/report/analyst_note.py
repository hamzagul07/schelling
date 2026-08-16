"""Pre-resolution analyst-note tables, computed from the sealed ledger and the committed rubric.

Session 58 (D58). A reading placed on record *before* an outcome is known, for a banded question:
for each plausible band, the graded value under the midpoint rule, every sealed record's resulting
error, and which family is closest; then the v2-vs-v1 sourcing comparison per band. Every figure is
computed here from the sealed medians (the ledger) and the pre-registered band midpoints (the
rubric) — none is typed. The note changes no grading rule and no sealed value; the rubric is
excluded from ``inputs_hash`` and the ledger medians are the published commitments — nothing moves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from schelling.report.rubric_lookup import parse_rubric_block

# A ledger row: | model | vintage | question | frozen_at | median | `sha` |
_LEDGER_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*[^|]+?\s*\|\s*([\d.]+)\s*\|"
)
_EN = "\u2013"  # en dash as an escape so the source has no confusable literal (RUF001)
# Short names for the four plausible bands, keyed by the rubric band's lower bound.
_PLAUSIBLE = {11.0: "Collapse", 31.0: "US terms", 45.0: "Balanced", 61.0: "Iranian-leaning"}
# The order sealed records are shown in — (family, vintage).
_RECORDS = [
    ("challenge", "v1"),
    ("challenge", "v2"),
    ("compromise", "v1"),
    ("compromise", "v2"),
    ("llm-judgment", "v2"),
]


@dataclass(frozen=True)
class _Band:
    name: str
    lo: float
    hi: float

    @property
    def midpoint(self) -> float:
        return (self.lo + self.hi) / 2


def sealed_medians(forecasts_md: str, question_id: str) -> dict[tuple[str, str], float]:
    """``{(family, vintage): median}`` for a question, from the committed ledger rows."""
    out: dict[tuple[str, str], float] = {}
    for line in forecasts_md.splitlines():
        m = _LEDGER_ROW.match(line)
        if m and m.group(3).strip() == question_id:
            out[(m.group(1).strip(), m.group(2).strip())] = float(m.group(4))
    return out


def plausible_bands(grading_md: str) -> list[_Band]:
    """The four plausible bands (collapse, US terms, balanced, Iranian-leaning), from the rubric."""
    rubric = parse_rubric_block(grading_md)
    if rubric is None:
        return []
    bands = [_Band(_PLAUSIBLE[b.lo], b.lo, b.hi) for b in rubric.bands if b.lo in _PLAUSIBLE]
    return sorted(bands, key=lambda b: b.lo)


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def _cols(medians: dict[tuple[str, str], float]) -> list[tuple[str, str]]:
    return [rec for rec in _RECORDS if rec in medians]


def outcome_table(medians: dict[tuple[str, str], float], bands: list[_Band]) -> str:
    """Table (a): per band — graded midpoint, each record's error, and the closest record."""
    cols = _cols(medians)
    head = (
        "| Plausible band | Graded (midpoint) | "
        + " | ".join(f"{fam} {vin}" for fam, vin in cols)
        + " | Closest |"
    )
    sep = "|---|---:|" + "".join("---:|" for _ in cols) + "---|"
    lines = [head, sep]
    for b in bands:
        errs = {rec: abs(medians[rec] - b.midpoint) for rec in cols}
        winner = min(cols, key=lambda rec: errs[rec])
        cells = " | ".join(_fmt(errs[rec]) for rec in cols)
        lines.append(
            f"| {b.name} ({b.lo:g}{_EN}{b.hi:g}) | {b.midpoint:g} | {cells} | "
            f"{winner[0]} {winner[1]} |"
        )
    return "\n".join(lines)


def _verdict(medians: dict[tuple[str, str], float], b: _Band, family: str) -> tuple[str, str]:
    """(cell, family-verdict) for one family in one band — does v2 beat v1?"""
    e1 = abs(medians[(family, "v1")] - b.midpoint)
    e2 = abs(medians[(family, "v2")] - b.midpoint)
    who = "v2 wins" if e2 < e1 else "v1 wins" if e1 < e2 else "tie"
    return f"{_fmt(e1)} → {_fmt(e2)} ({who})", who


def sourcing_table(medians: dict[tuple[str, str], float], bands: list[_Band]) -> str:
    """Table (b): per band, whether the v2-beats-v1 (sourced-beats-thin) finding replicates."""
    families = [
        f for f in ("challenge", "compromise") if (f, "v1") in medians and (f, "v2") in medians
    ]
    head = (
        "| Plausible band | "
        + " | ".join(f"{f}: v1 err → v2 err" for f in families)
        + " | Sourcing (v2 beats v1?) |"
    )
    sep = "|---|" + "".join("---|" for _ in families) + "---|"
    lines = [head, sep]
    for b in bands:
        cells, verdicts = [], []
        for f in families:
            cell, who = _verdict(medians, b, f)
            cells.append(cell)
            verdicts.append(who)
        wins = [v == "v2 wins" for v in verdicts]
        if all(wins):
            band_verdict = "REPLICATES"
        elif not any(wins):
            band_verdict = "FAILS"
        else:
            band_verdict = "SPLIT"
        lines.append(
            f"| {b.name} ({b.lo:g}{_EN}{b.hi:g}) | " + " | ".join(cells) + f" | {band_verdict} |"
        )
    return "\n".join(lines)


def render_note_tables(forecasts_md: str, grading_md: str, question_id: str) -> str:
    """Both computed tables, for embedding in the analyst note (pure; every figure derived)."""
    medians = sealed_medians(forecasts_md, question_id)
    bands = plausible_bands(grading_md)
    return (
        "**Table (a) — graded value and each record's error, per plausible band.**\n\n"
        + outcome_table(medians, bands)
        + "\n\n**Table (b) — does the v2-beats-v1 sourcing finding replicate, per band?**\n\n"
        + sourcing_table(medians, bands)
    )
