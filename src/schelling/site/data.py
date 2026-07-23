"""Gather every figure the site quotes from the repository's own artifacts (D31.1).

Nothing here invents a number. Each field is parsed from a committed artifact — the sealed ledger,
the backtest, the evidence table (whose ``E-TESTS`` row supplies the test count), the decisions log.
:func:`gather` reads only committed files (no git, no pytest subprocess, no wall clock), so it is a
pure function of the tree: ``site build`` regenerates byte-for-byte and ``--check`` is stable across
the very commit that publishes the site — which a live HEAD stamp would not be (D31.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from schelling.paper.assemble import parse_evidence
from schelling.report.rubric_lookup import parse_rubric_block
from schelling.schemas.question import RubricBand

_LEDGER = re.compile(r"<!-- LEDGER:START -->(.*?)<!-- LEDGER:END -->", re.DOTALL)
_LEADERBOARD = re.compile(r"<!-- LEADERBOARD:START -->(.*?)<!-- LEADERBOARD:END -->", re.DOTALL)
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
# A standalone figure: a sign counts only when not glued to a preceding word char or dot, so the
# hyphens in ``utf-8``, ``SHA-256`` and ``Q-2026`` are read as text, not as negative signs, and a
# digit inside a hex hash (preceded by a letter) is not a figure at all.
_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class LedgerRow:
    """One sealed forecast: a row of the ``FORECASTS.md`` commit-reveal table."""

    model: str
    vintage: str
    question: str
    frozen_at: str
    median: str
    sha256: str


@dataclass(frozen=True)
class ReportLink:
    """A rendered dossier/report copied into ``docs/reports/``."""

    filename: str
    title: str


@dataclass(frozen=True)
class QuestionInfo:
    """A sealed question: where its pre-registered rubric lives and when it resolves."""

    question_id: str
    rubric_file: str
    resolution_date: str


@dataclass
class SiteData:
    """Everything the pages quote, each field traced to a repository artifact."""

    decisions_count: int = 0
    test_count: str = ""
    resolution_date: str = ""
    grading_date: str = ""
    ledger: list[LedgerRow] = field(default_factory=list)
    graded_questions: frozenset[str] = frozenset()
    evidence: dict[str, dict[str, str]] = field(default_factory=dict)
    gate_verdict: str = ""
    successor_verdict: str = ""
    leaderboard_header: list[str] = field(default_factory=list)
    leaderboard_rows: list[list[str]] = field(default_factory=list)
    abstract: str = ""
    bibliography: list[str] = field(default_factory=list)
    reports: list[ReportLink] = field(default_factory=list)
    questions: dict[str, QuestionInfo] = field(default_factory=dict)
    # Instrument layer (Session 34): the 80% interval of each sealed forecast, keyed by ledger
    # SHA-256 (from the committed FORECAST-INTERVALS.json snapshot), and each question's rubric band
    # boundaries (from its committed GRADING file). Both feed the hero figure; both are committed.
    intervals: dict[str, tuple[float, float]] = field(default_factory=dict)
    rubric_bands: dict[str, list[RubricBand]] = field(default_factory=dict)

    # ------------------------------------------------------------------ derived counts
    @property
    def sealed_count(self) -> int:
        """How many forecasts are sealed in the ledger (one per row)."""
        return len(self.ledger)

    @property
    def graded_count(self) -> int:
        """How many sealed forecasts have been graded — 0 until an outcome is recorded (D31.5)."""
        return sum(1 for row in self.ledger if row.question in self.graded_questions)

    # ------------------------------------------------------------------ evidence access
    def fig(self, tag: str) -> str:
        """The value of one evidence tag (empty string when absent, never a guess)."""
        return self.evidence.get(tag, {}).get("value", "")

    def provenance(self) -> set[str]:
        """Every figure the site is entitled to print — the audit whitelist for the
        no-hand-typed-figures test (D31.6). Holds each artifact string AND its numeric sub-tokens,
        so a statistic drawn from a compound evidence value (``26.83 / 38.51``) is whitelisted as
        ``26.83`` too. If a number appears in the HTML and not here, it was not sourced from an
        artifact."""
        strings: set[str] = set()
        for row in self.ledger:
            strings.update({row.median, row.sha256, row.sha256[:12], row.frozen_at, row.vintage})
        for info in self.questions.values():
            strings.add(info.resolution_date)
        for cells in self.leaderboard_rows:
            strings.update(cells)
        for rec in self.evidence.values():
            strings.add(rec.get("value", ""))
            strings.add(rec.get("prov", ""))
        # Verbatim artifact quotes: the abstract, the bibliography, and the leaderboard verdict are
        # copied word-for-word from paper/ and BACKTEST.md, so their numbers are already sourced.
        strings.add(self.abstract)
        strings.add(self.successor_verdict)
        strings.update(self.bibliography)
        strings.update(
            {
                str(self.decisions_count),
                self.test_count,
                self.resolution_date,
                self.grading_date,
                str(self.sealed_count),
                str(self.graded_count),
            }
        )
        out = set(strings)
        for s in strings:
            out.update(_NUM.findall(s))
        out.discard("")
        return out


def _parse_ledger(forecasts_md: str) -> list[LedgerRow]:
    block = _LEDGER.search(forecasts_md)
    if block is None:
        return []
    rows: list[LedgerRow] = []
    for line in block.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] in {"model", "---"} or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(
            LedgerRow(
                model=cells[0],
                vintage=cells[1],
                question=cells[2],
                frozen_at=cells[3],
                median=cells[4],
                sha256=cells[5].strip("`"),
            )
        )
    return rows


def _parse_leaderboard(backtest_md: str) -> tuple[list[str], list[list[str]], str]:
    """The successor-search leaderboard table (header, rows) and the bold verdict beneath it."""
    block = _LEADERBOARD.search(backtest_md)
    if block is None:
        return [], [], ""
    header: list[str] = []
    rows: list[list[str]] = []
    verdict = ""
    for line in block.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if set("".join(cells)) <= {"-", ":", " "}:
                continue  # the |---|---| separator row
            if not header:
                header = cells
            else:
                rows.append(cells)
        elif stripped.startswith("**") and not verdict:
            verdict = stripped.strip("*").strip()
    return header, rows, verdict


def _parse_dates(forecasts_md: str) -> tuple[str, str]:
    res = re.search(r"Resolution date:\s*\**\s*(\d{4}-\d{2}-\d{2})", forecasts_md)
    grade = re.search(r"Grading date:\s*\**\s*(\d{4}-\d{2}-\d{2})", forecasts_md)
    return (res.group(1) if res else "", grade.group(1) if grade else "")


def _parse_abstract(draft_md: str) -> str:
    """The single abstract paragraph from ``paper/DRAFT.md`` (between ``## Abstract`` and the next
    heading), with the paper's ``[^ev-...]`` provenance footnote markers stripped for display."""
    match = re.search(r"##\s*Abstract\s*\n+(.*?)\n#", draft_md, re.DOTALL)
    if match is None:
        return ""
    text = re.sub(r"\[\^ev-[^\]]+\]", "", match.group(1))
    return " ".join(text.split())


def _parse_bibliography(bib_md: str) -> list[str]:
    return [
        line.strip()[2:].strip() for line in bib_md.splitlines() if line.strip().startswith("- ")
    ]


def _graded_questions(repo_root: Path) -> frozenset[str]:
    """Questions whose outcome has been recorded. A ``GRADING-<qid>.md`` counts as graded only once
    it carries an ``**Actual outcome:**`` line — pre-registered rubrics alone do not (D31.5). None
    are graded until resolution, so this is empty today and the honesty rules engage."""
    graded: set[str] = set()
    for path in sorted(repo_root.glob("GRADING-*.md")):
        if re.search(
            r"^\s*\**\s*Actual outcome\s*:", path.read_text(), re.MULTILINE | re.IGNORECASE
        ):
            graded.add(path.stem.replace("GRADING-", ""))
    return frozenset(graded)


def _questions(repo_root: Path, ledger: list[LedgerRow]) -> dict[str, QuestionInfo]:
    """One entry per distinct sealed question, in ledger order, linking its pre-registered rubric
    and reading its resolution date from that rubric file."""
    out: dict[str, QuestionInfo] = {}
    for row in ledger:
        if row.question in out:
            continue
        rubric = f"GRADING-{row.question}.md"
        resolution = ""
        rubric_path = repo_root / rubric
        if rubric_path.exists():
            dates = _DATE.findall(rubric_path.read_text())
            resolution = max(dates) if dates else ""
        out[row.question] = QuestionInfo(row.question, rubric, resolution)
    return out


def _reports(repo_root: Path) -> list[ReportLink]:
    """Rendered reports present in ``docs/reports/`` (committed inputs), titled from their
    ``<title>``, sorted by filename for determinism."""
    reports_dir = repo_root / "docs" / "reports"
    if not reports_dir.exists():
        return []
    out: list[ReportLink] = []
    for path in sorted(reports_dir.glob("*.html")):
        if path.name == "index.html":
            continue
        match = _TITLE.search(path.read_text())
        title = " ".join(match.group(1).split()) if match else path.stem
        out.append(ReportLink(path.name, title))
    return out


def gather(repo_root: Path) -> SiteData:
    """Parse every site figure from the repository's artifacts (a pure function of the tree)."""
    forecasts = (repo_root / "FORECASTS.md").read_text()
    backtest = (repo_root / "BACKTEST.md").read_text()
    evidence = parse_evidence((repo_root / "paper" / "EVIDENCE.md").read_text())
    decisions = (repo_root / "DECISIONS.md").read_text()

    ledger = _parse_ledger(forecasts)
    resolution_date, grading_date = _parse_dates(forecasts)
    lb_header, lb_rows, successor_verdict = _parse_leaderboard(backtest)
    gate = re.search(r"\*\*Verdict:\s*([A-Z]+)", backtest)

    draft_path = repo_root / "paper" / "DRAFT.md"
    bib_path = repo_root / "paper" / "BIBLIOGRAPHY.md"

    from schelling.site.intervals import load_intervals  # local: intervals imports from this module

    questions = _questions(repo_root, ledger)
    rubric_bands = _rubric_bands(repo_root, questions)

    return SiteData(
        decisions_count=sum(1 for line in decisions.splitlines() if line.startswith("### D")),
        test_count=evidence.get("E-TESTS", {}).get("value", ""),
        resolution_date=resolution_date,
        grading_date=grading_date,
        ledger=ledger,
        graded_questions=_graded_questions(repo_root),
        evidence=evidence,
        gate_verdict=gate.group(1) if gate else "",
        successor_verdict=successor_verdict,
        leaderboard_header=lb_header,
        leaderboard_rows=lb_rows,
        abstract=_parse_abstract(draft_path.read_text()) if draft_path.exists() else "",
        bibliography=_parse_bibliography(bib_path.read_text()) if bib_path.exists() else [],
        reports=_reports(repo_root),
        questions=questions,
        intervals=load_intervals(repo_root),
        rubric_bands=rubric_bands,
    )


def _rubric_bands(
    repo_root: Path, questions: dict[str, QuestionInfo]
) -> dict[str, list[RubricBand]]:
    """Each sealed question's rubric band boundaries, parsed from its committed GRADING file."""
    out: dict[str, list[RubricBand]] = {}
    for qid, info in questions.items():
        path = repo_root / info.rubric_file
        if not path.exists():
            continue
        rubric = parse_rubric_block(path.read_text())
        if rubric is not None and rubric.bands:
            out[qid] = sorted(rubric.bands, key=lambda b: b.lo)
    return out
