"""Pre-registered comparison of forecast families on the live sealed ledger (Session 27, D27.4).

Compare |median - actual| across the three families — challenge, compromise, and llm-judgment —
on graded questions from the live ledger. **Exploratory until at least 10 graded questions**: no
verdict is claimed and the harness REFUSES to print a ranking before then, the same discipline the
coercive reading holds to (D20). Contaminated runs (D27.5) never reach the live ledger, so it stays
clean.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

# The comparison stays exploratory — no ranking — until this many graded questions accrue.
MIN_GRADED = 10
FAMILIES = ("challenge", "compromise", "llm-judgment")

_LEDGER_ROW = re.compile(
    r"^\|\s*(?P<model>[\w-]+)\s*\|\s*(?P<vintage>[\w—-]+)\s*\|\s*(?P<q>[\w-]+)\s*\|"
    r"\s*(?P<frozen>[\w-]+)\s*\|\s*(?P<median>[\d.]+)\s*\|"
)


@dataclass(frozen=True)
class FamilyScore:
    family: str
    mae: float
    n: int


@dataclass(frozen=True)
class Comparison:
    """The comparison outcome: exploratory (no ranking) until MIN_GRADED, then ranked by MAE."""

    graded_count: int
    ready: bool
    scores: list[FamilyScore] = field(default_factory=list)  # ranked best-first; empty until ready
    note: str = ""


def parse_ledger_medians(ledger_text: str) -> dict[tuple[str, str], float]:
    """``(family, question) -> median`` from the ledger, keeping the latest row for each pair."""
    out: dict[tuple[str, str], float] = {}
    for line in ledger_text.splitlines():
        m = _LEDGER_ROW.match(line)
        if m:
            out[(m["model"], m["q"])] = float(m["median"])
    return out


def compare_baselines(ledger_text: str, grades: dict[str, float]) -> Comparison:
    """Compare the families on questions that are graded AND sealed for all three (D27.4).

    ``grades`` maps ``question_id -> actual`` (the resolved outcome on the 0-100 continuum).
    Returns an exploratory :class:`Comparison` (no ranking) until ``MIN_GRADED`` questions exist.
    """
    medians = parse_ledger_medians(ledger_text)
    graded_qs = sorted(q for q in grades if all((fam, q) in medians for fam in FAMILIES))
    n = len(graded_qs)
    if n < MIN_GRADED:
        return Comparison(
            graded_count=n,
            ready=False,
            note=(
                f"Exploratory: {n}/{MIN_GRADED} questions graded with all three families sealed. "
                "No ranking is claimed before the threshold — the same discipline the coercive "
                "reading holds to. The live sealed ledger is the clean comparison venue; "
                "contamination-risk runs are excluded by construction."
            ),
        )
    scores = [
        FamilyScore(
            family=fam,
            mae=float(statistics.fmean(abs(medians[(fam, q)] - grades[q]) for q in graded_qs)),
            n=n,
        )
        for fam in FAMILIES
    ]
    scores.sort(key=lambda s: (s.mae, s.family))
    return Comparison(
        graded_count=n,
        ready=True,
        scores=scores,
        note=f"Ranking over {n} graded questions (>= {MIN_GRADED}); lower MAE is better.",
    )
