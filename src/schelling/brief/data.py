"""Gather every figure a brief quotes, from the committed artifacts (Session 56, D56).

Nothing here is hand-typed. The actual outcome and its citation come from the grading file's
GRADED block in ``FORECASTS.md``; each record's median, vintage, model and error from that same
block; the barrels column by INVERTING the rubric's ``outcome_map`` (never transcribed); the seal,
resolution and grading dates from the ledger. :func:`gather_brief` refuses an ungraded question by
raising :class:`BriefNotGradedError` — the command's refusal path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from schelling.backtest.mapping import round_half_up
from schelling.report.rubric_lookup import lookup_rubric

# A standalone number for the provenance whitelist — a sign counts only when not glued to a word
# char or dot (so the hyphens in ``Q-2026`` and ``SHA-256`` are text, not signs). Mirrors site.data.
_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?")

_ACTUAL = re.compile(
    r"\*\*Actual outcome:\*\*\s*(?P<raw>-?[\d.]+)\D+?continuum\s*\*\*(?P<cont>-?[\d.]+)\*\*"
)
# model | vintage | median | primary(|med-actual|) | ... — captures the median and the error.
_ROW = re.compile(
    r"^\|\s*(?P<model>challenge|compromise|llm-judgment)\s*\|\s*"
    r"(?P<vintage>v1-thin|v2-sourced)\s*\|\s*(?P<median>[\d.]+)\s*\|\s*"
    r"(?P<error>[\d.]+)\s*\|"
)
_JUST = re.compile(r"\*\*Justification\.\*\*\s*(?P<text>.+?)(?:\n\n|\Z)", re.DOTALL)
_CITE = re.compile(r"\*\*Citations\.\*\*\s*(?P<text>.+?)(?:\n\n|\Z)", re.DOTALL)
_GRADING_DATE = re.compile(r"Grading date:\s*\**\s*(\d{4}-\d{2}-\d{2})")
_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_DATE_LONG = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b")

_METHOD_LABEL = {
    "challenge": "Challenge model",
    "compromise": "Compromise model",
    "llm-judgment": "AI judgement",
}
_EVIDENCE_LABEL = {"v1-thin": "thin", "v2-sourced": "researched"}
_FAMILY = {"challenge": "challenge", "compromise": "compromise", "llm-judgment": "llm"}

_DIV = "\u00f7"  # division sign as an escape so the source has no confusable literal (RUF001)
_MUL = "\u00d7"  # multiplication sign


class BriefNotGradedError(ValueError):
    """Raised when a brief is requested for a question with no recorded outcome (the refusal)."""


class BriefUnsupportedError(ValueError):
    """Raised when a graded question has no arithmetic ``outcome_map`` to invert for barrels."""


def slug_for(question_id: str) -> str:
    """The brief's file stem: the question id lower-cased (``Q-2026-OPEC-SEP`` -> ``q-2026-opec-sep``)."""  # noqa: E501
    return question_id.strip().lower()


@dataclass(frozen=True)
class RecordFig:
    """One graded record's figures, as published in the GRADED table."""

    model: str  # challenge | compromise | llm-judgment
    vintage: str  # v1-thin | v2-sourced
    median: float
    error: float  # |median - actual continuum|

    @property
    def family(self) -> str:
        return _FAMILY[self.model]

    @property
    def method_label(self) -> str:
        return _METHOD_LABEL[self.model]

    @property
    def evidence_label(self) -> str:
        return _EVIDENCE_LABEL[self.vintage]

    @property
    def researched(self) -> bool:
        return self.vintage == "v2-sourced"


@dataclass(frozen=True)
class BriefData:
    """Every figure a brief prints, each traced to a committed artifact."""

    question_id: str
    slug: str
    actual_raw: float  # announced adjustment, in the rubric's unit (thousand b/d)
    actual_continuum: float  # the graded 0-100 settlement (rounded)
    actual_continuum_unrounded: float  # before the rubric's rounding — for the honest caveat
    unit: str  # the outcome_map unit string
    justification: str
    citation: str  # the outcome's source (URL), from the GRADED block
    seal_date: str  # "24 July 2026" — from the ledger's frozen_at
    resolved_date: str  # "2 August 2026" — the announcement date, from the justification
    grade_date: str  # "6 August 2026" — from the ledger's Grading date
    slope: float  # outcome_map slope (continuum units per unit of raw)
    intercept: float  # outcome_map intercept
    records: tuple[RecordFig, ...]  # in GRADED-table order

    # ------------------------------------------------------------------ inversions / derivations
    def barrels_kbd(self, median: float) -> int:
        """Invert the rubric's linear map: the raw adjustment (thousand b/d) a continuum implies."""
        return int(round_half_up((median - self.intercept) / self.slope))

    def barrels_display(self, median: float) -> str:
        """The inverted adjustment as whole barrels/day, comma-grouped (``66.0`` -> ``192,000``)."""
        return f"{self.barrels_kbd(median) * 1000:,}"

    @property
    def best_record(self) -> RecordFig:
        """The record closest to the outcome (smallest error) — shown red in table and chart."""
        return min(self.records, key=lambda r: (r.error, not r.researched))

    @property
    def llm_shift(self) -> float:
        """How far the AI-judgement median moved from thin to researched inputs (the |shift|)."""
        by_v = {r.vintage: r.median for r in self.records if r.model == "llm-judgment"}
        return abs(by_v.get("v2-sourced", 0.0) - by_v.get("v1-thin", 0.0))

    # ------------------------------------------------------------------ prose tag resolution
    def tag_values(self) -> dict[str, str]:
        """The ``{{tag}}`` values the prose may reference — each one a computed figure."""
        denom = self.intercept / self.slope  # 600: the divisor of the rubric's canonical formula
        formula = (
            f"grade = {self.intercept:g} + (barrels {_DIV} {denom:g}) {_MUL} {self.intercept:g}"
        )
        best = self.best_record
        return {
            "question_id": self.question_id,
            "outcome": f"{self.actual_continuum:g}",
            "barrels_actual": f"{int(round_half_up(self.actual_raw)) * 1000:,}",
            "grade_formula": formula,
            "seal_date": self.seal_date,
            "resolved_date": self.resolved_date,
            "grade_date": self.grade_date,
            "llm_shift": f"{self.llm_shift:g}",
            "actual_raw_continuum": f"{self.actual_continuum_unrounded:.2f}",
            "best_median": f"{best.median:.1f}",
        }

    # ------------------------------------------------------------------ provenance whitelist
    def provenance(self) -> set[str]:
        """Every number the brief is entitled to print — the audit set for the no-hand-typed test.

        Holds each figure string AND its numeric sub-tokens, so a comma-grouped ``192,000`` or a
        dated ``2 August 2026`` whitelists ``192``/``000`` and ``2``/``2026`` too. Any number in the
        HTML (outside the chart/style, which are computed) that is absent here was not sourced.
        """
        strings: set[str] = set(self.tag_values().values())
        strings.update({self.question_id, self.citation, str(len(self.records))})
        for r in self.records:
            strings.add(f"{r.median:.2f}")
            strings.add(self.barrels_display(r.median))
            strings.add(f"{r.error:.2f}")
        out = set(strings)
        for s in strings:
            out.update(_NUM.findall(s))
        out.discard("")
        return out


def _fmt_iso(iso: str) -> str:
    """``2026-07-24`` -> ``24 July 2026`` (no leading zero on the day)."""
    year, month, day = iso.split("-")
    return f"{int(day)} {_MONTHS[int(month) - 1]} {year}"


def _graded_block(forecasts_md: str, question_id: str) -> str | None:
    """The GRADED block for ``question_id`` from FORECASTS.md, or ``None`` if the question is
    ungraded (no such block)."""
    header = f"### GRADED — {question_id}"  # em-dash, matching render_grade_block
    start = forecasts_md.find(header)
    if start == -1:
        return None
    block = forecasts_md[start:]
    nxt = block.find("\n### ", 1)
    return block[:nxt] if nxt != -1 else block


def _seal_date(forecasts_md: str, question_id: str) -> str:
    """The seal date from the ledger's frozen_at column for this question (a range if not one)."""
    dates = sorted(
        {
            m.group(1)
            for line in forecasts_md.splitlines()
            if question_id in line
            for m in [re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", line)]
            if m
        }
    )
    if not dates:
        return ""
    if len(dates) == 1:
        return _fmt_iso(dates[0])
    return f"{_fmt_iso(dates[0])} to {_fmt_iso(dates[-1])}"


def gather_brief(question_id: str, repo_root: Path) -> BriefData:
    """Parse every figure for ``question_id``'s brief from the committed artifacts.

    Raises :class:`BriefNotGradedError` when the question has no recorded outcome (the refusal),
    or :class:`BriefUnsupportedError` when a graded question carries no arithmetic ``outcome_map``.
    """
    forecasts = (repo_root / "FORECASTS.md").read_text()
    block = _graded_block(forecasts, question_id)
    if block is None:
        raise BriefNotGradedError(
            f"{question_id} is not graded — no '### GRADED' block in FORECASTS.md; "
            "a brief is only for a resolved, graded question."
        )
    actual = _ACTUAL.search(block)
    if actual is None:
        raise BriefNotGradedError(
            f"{question_id}: GRADED block present but its Actual-outcome line is unparseable."
        )

    looked = lookup_rubric(question_id, repo_root)
    if looked is None:
        raise BriefUnsupportedError(f"{question_id}: no grading rubric found for the outcome map.")
    rubric, _source = looked
    if rubric.outcome_map is None:
        raise BriefUnsupportedError(
            f"{question_id}: the rubric has no arithmetic outcome_map to invert for barrels."
        )
    omap = rubric.outcome_map

    actual_raw = float(actual["raw"])
    records = tuple(
        RecordFig(m["model"], m["vintage"], float(m["median"]), float(m["error"]))
        for line in block.splitlines()
        for m in [_ROW.match(line)]
        if m
    )
    if not records:
        raise BriefNotGradedError(f"{question_id}: GRADED block has no scored record rows.")

    just = _JUST.search(block)
    justification = " ".join(just["text"].split()) if just else ""
    cite = _CITE.search(block)
    citation = " ".join(cite["text"].split()) if cite else ""
    ann = _DATE_LONG.search(justification)
    resolved_date = f"{int(ann.group(1))} {ann.group(2)} {ann.group(3)}" if ann else ""
    grading = _GRADING_DATE.search(forecasts)

    return BriefData(
        question_id=question_id,
        slug=slug_for(question_id),
        actual_raw=actual_raw,
        actual_continuum=float(actual["cont"]),
        actual_continuum_unrounded=omap.intercept + omap.slope * actual_raw,
        unit=omap.unit,
        justification=justification,
        citation=citation,
        seal_date=_seal_date(forecasts, question_id),
        resolved_date=resolved_date,
        grade_date=_fmt_iso(grading.group(1)) if grading else "",
        slope=omap.slope,
        intercept=omap.intercept,
        records=records,
    )
