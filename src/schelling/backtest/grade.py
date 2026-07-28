"""Grade a resolved question against its committed rubric (Session 49, D49.0).

The real grading path (the D48 rehearsal is now closed). ``grade_question`` orchestrates the pieces
that already exist and gates on integrity:

1. **verify every sealed row** — schema-dispatched, so solver, llm-judgment, and crowd rows are all
   verifiable (D49.1).
2. **check the OpenTimestamps proof** three ways (D49.3): (a) proof MISSING and (b) proof present
   but HASH-MISMATCH both block grading; (c) attestation retrieved but unconfirmable locally (no
   Bitcoin node) does NOT block — it reports "calendar attestation retrieved, full verification
   requires a node".
3. **map the outcome** onto the 0-100 continuum via the rubric's machine-readable ``outcome_map``
   (D49.2), read from the committed grading file — never transcribed by hand.
4. **score every row** — solver/llm on the continuum, crowd on the binary track (D47.2).

Nothing is written unless every blocking check passes. On write the grade goes into BOTH
FORECASTS.md and the grading file's ``**Actual outcome:**`` line atomically (D49.5), and the ledger
is re-stamped so the anchor tracks the new bytes (D49.4).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from schelling.backtest.ledger import record_sha256
from schelling.backtest.mapping import map_outcome
from schelling.backtest.scoring import (
    ScoreCard,
    binary_prob_met,
    binary_realized,
    brier_binary,
    score_record,
)
from schelling.backtest.verify import verify_record
from schelling.report.rubric_lookup import lookup_rubric
from schelling.schemas.forecast import (
    CrowdForecastRecord,
    ForecastRecord,
    LLMForecastRecord,
)
from schelling.schemas.question import ResolutionRubric


# ----------------------------------------------------------------- OpenTimestamps (D49.3/D49.4)
def _ots_binary() -> str | None:
    """Locate the ``ots`` client, resolving the D48.4 PATH discrepancy (D49.3).

    ``opentimestamps-client`` installs the ``ots`` console script next to the interpreter running
    schelling, so it is present in the venv even when a bare shell's PATH does not include it. Look
    there first (``sys.executable``'s directory), then fall back to PATH.
    """
    candidate = Path(sys.executable).with_name("ots")
    if candidate.exists():
        return str(candidate)
    return shutil.which("ots")


def classify_ots_output(returncode: int, output: str) -> tuple[str, bool]:
    """Classify ``ots verify`` output into a status + whether it BLOCKS grading (D49.3, pure).

    Returns one of: ``confirmed`` (Bitcoin anchor verified), ``attestation_only`` (calendar
    attestation retrieved but not confirmable locally — no node/pending), ``mismatch`` (the proof is
    for different bytes). Only ``mismatch`` blocks here; ``missing`` is detected before this runs.
    """
    low = output.lower()
    if returncode == 0 or "success!" in low:
        return "confirmed", False
    # A digest mismatch means the proof does not belong to these bytes — a real integrity failure.
    if ("expected" in low and "got" in low) or "does not match" in low or "failed!" in low:
        return "mismatch", True
    # A calendar commitment exists but the Bitcoin anchor is not confirmable locally — non-blocking:
    #   * "pending confirmation in Bitcoin blockchain" — stamped, awaiting a Bitcoin block;
    #   * "could not connect to Bitcoin node" — confirmable, but no local node to check against;
    #   * "attestation" retrieved from a calendar / cache.
    if "pending" in low or "could not connect to bitcoin" in low or "attestation" in low:
        return "attestation_only", False
    # Nothing recognisable — be conservative and block (treat as an unverifiable proof).
    return "mismatch", True


@dataclass
class OtsResult:
    status: str  # confirmed | attestation_only | missing | mismatch | no_client
    blocks: bool
    note: str


def check_ots(ledger_path: Path, proofs_dir: Path) -> OtsResult:
    """Three-way OpenTimestamps check for the CURRENT ledger bytes (D49.3)."""
    fsha = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    proof = proofs_dir / f"{ledger_path.name}-{fsha[:12]}.ots"
    if not proof.exists():  # (a) missing — blocks
        return OtsResult(
            "missing",
            True,
            f"NO proof for the current ledger state (sha {fsha[:12]}…) in {proofs_dir}/",
        )
    ots = _ots_binary()
    if ots is None:
        return OtsResult(
            "no_client",
            False,
            f"proof {proof.name} present, but the `ots` client is not installed — calendar "
            "attestation cannot be checked locally; full verification requires it",
        )
    result = subprocess.run(
        [ots, "verify", str(proof), "-f", str(ledger_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    status, blocks = classify_ots_output(
        result.returncode, (result.stderr or "") + (result.stdout or "")
    )
    notes = {
        "confirmed": "`ots verify` confirmed the Bitcoin anchor.",
        "attestation_only": "calendar attestation retrieved, full verification requires a node.",
        "mismatch": f"proof does NOT match ledger bytes (sha {fsha[:12]}…) — integrity fail.",
    }
    return OtsResult(status, blocks, notes[status])


# ------------------------------------------------------------------------------------ the grade
@dataclass
class RecordGrade:
    model: str
    vintage: str
    sha: str
    record_path: Path | None
    record_type: str  # forecast | llm-judgment | crowd-metaculus | MISSING
    verify_ok: bool
    verify_notes: list[str]
    card: ScoreCard | None  # continuum score (forecast/llm); None for crowd/missing
    binary_brier: float | None = None  # crowd binary-track Brier, when applicable


@dataclass
class GradeReport:
    question_id: str
    actual_raw: float
    actual_continuum: float
    mapping_note: str
    justification: str
    citations: list[str]
    rubric_source: str
    ots: OtsResult
    grades: list[RecordGrade] = field(default_factory=list)

    @property
    def integrity_ok(self) -> bool:
        return not self.ots.blocks and all(g.verify_ok for g in self.grades)


def _ledger_rows_for(ledger_text: str, question_id: str) -> list[tuple[str, str, str]]:
    """(model, vintage, sha) for every ledger row of ``question_id``, in ledger order."""
    import re

    row = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|.*\|\s*`([0-9a-f]{64})`")
    out = []
    for line in ledger_text.splitlines():
        m = row.match(line)
        if m and m.group(3) == question_id:
            out.append((m.group(1), m.group(2), m.group(4)))
    return out


def _find_record(runs_dir: Path, sha: str) -> Path | None:
    for path in sorted(runs_dir.glob("*.json")):
        if record_sha256(path) == sha:
            return path
    return None


def _load_and_type(path: Path) -> tuple[str, object]:
    """Return (family, record) for a sealed record file, dispatching on schema."""
    text = path.read_text()
    for cls, label in (
        (ForecastRecord, "forecast"),
        (LLMForecastRecord, "llm-judgment"),
        (CrowdForecastRecord, "crowd-metaculus"),
    ):
        try:
            return label, cls.model_validate_json(text)
        except ValueError:
            continue
    return "UNKNOWN", object()


def grade_question(
    question_id: str,
    actual_raw: float,
    justification: str,
    citations: list[str],
    repo_root: Path,
) -> GradeReport:
    """Verify, map, and score every sealed record for a question. Pure — writes nothing (D49.0)."""
    ledger_path = repo_root / "FORECASTS.md"
    runs_dir = repo_root / "runs"
    proofs_dir = repo_root / "ledger-proofs"
    ledger_text = ledger_path.read_text()

    looked = lookup_rubric(question_id, repo_root)
    rubric: ResolutionRubric | None = looked[0] if looked else None
    rubric_source = looked[1] if looked else "(no grading file found)"
    actual_continuum, mapping_note = map_outcome(rubric, actual_raw)

    ots = check_ots(ledger_path, proofs_dir)

    grades: list[RecordGrade] = []
    for model, vintage, sha in _ledger_rows_for(ledger_text, question_id):
        path = _find_record(runs_dir, sha)
        if path is None:
            grades.append(
                RecordGrade(
                    model,
                    vintage,
                    sha,
                    None,
                    "MISSING",
                    False,
                    ["record file not found in runs/ — cannot verify or score"],
                    None,
                )
            )
            continue
        family, record = _load_and_type(path)
        report = verify_record(path, ledger_path)
        card: ScoreCard | None = None
        binary: float | None = None
        if isinstance(record, CrowdForecastRecord):
            met = binary_realized(actual_continuum, rubric)
            if met is not None:
                binary = brier_binary(record.binary_prob_met, met)
        elif isinstance(record, ForecastRecord | LLMForecastRecord):
            card = score_record(record, actual_continuum)
            # a derived binary Brier too, when the question declares a binary mapping (D47.1)
            p = binary_prob_met(record, rubric) if isinstance(record, ForecastRecord) else None
            met = binary_realized(actual_continuum, rubric)
            if p is not None and met is not None:
                binary = brier_binary(p, met)
        grades.append(
            RecordGrade(
                model,
                vintage,
                sha,
                path,
                family,
                report.ok,
                [f"{c.name}: {'PASS' if c.passed else 'FAIL'}" for c in report.checks],
                card,
                binary,
            )
        )

    return GradeReport(
        question_id,
        actual_raw,
        actual_continuum,
        mapping_note,
        justification,
        list(citations),
        rubric_source,
        ots,
        grades,
    )


def actual_outcome_line(report: GradeReport) -> str:
    """The ``**Actual outcome:**`` line — the SINGLE graded-state marker the site reads too (D49.5).

    ``site.data._graded_questions`` counts a question graded exactly when its grading file carries a
    line matching ``^\\s*\\**\\s*Actual outcome\\s*:``; this writes one, so the grade command's two
    writes (ledger + grading file) leave a single, consistent notion of "graded".
    """
    return (
        f"**Actual outcome:** {report.actual_raw:g} → continuum {report.actual_continuum:g}. "
        f"{report.justification} (graded {report.question_id}; see FORECASTS.md)."
    )


def write_grade(report: GradeReport, ledger_path: Path, grading_path: Path) -> None:
    """Write the grade into BOTH FORECASTS.md and the grading file atomically (D49.5).

    Both new contents are built first, then both files are written, so graded state can never land
    in only one of them. Re-stamping (D49.4) is the caller's final step.
    """
    new_ledger = ledger_path.read_text().rstrip() + "\n\n" + render_grade_block(report)
    new_grading = grading_path.read_text().rstrip() + "\n\n" + actual_outcome_line(report) + "\n"
    ledger_path.write_text(new_ledger)
    grading_path.write_text(new_grading)


def render_grade_block(report: GradeReport) -> str:
    """The markdown block the grade writes into FORECASTS.md (D49.5)."""
    lines = [
        f"### GRADED — {report.question_id}",
        "",
        f"**Actual outcome:** {report.actual_raw:g} → continuum **{report.actual_continuum:g}**. "
        f"{report.mapping_note} (rubric: {report.rubric_source}).",
        "",
        f"**Justification.** {report.justification}",
        "",
        "**Citations.** " + (" · ".join(report.citations) if report.citations else "(none)"),
        "",
        f"**Integrity.** OTS [{report.ots.status}]: {report.ots.note} "
        f"Every sealed record was re-verified at grading; see the per-record integrity column.",
        "",
        "| model | vintage | median | primary \\|med-actual\\| | secondary | binary | integrity |",
        "|---|---|---:|---:|---|---:|---|",
    ]
    for g in report.grades:
        binary = f"{g.binary_brier:.4f}" if g.binary_brier is not None else "—"
        integ = "PASS" if g.verify_ok else "FAIL"
        if g.card is None:
            median = "—" if g.record_type != "crowd-metaculus" else "(binary)"
            notes = "; ".join(g.verify_notes)
            lines.append(
                f"| {g.model} | {g.vintage} | {median} | — | {notes} | {binary} | {integ} |"
            )
            continue
        prim = g.card.primary
        pv = f"{prim.value:.3f}" if prim else "—"
        sec = ", ".join(f"{s.name} {s.value:.3f}" for s in g.card.secondary) or "—"
        lines.append(
            f"| {g.model} | {g.vintage} | {g.card.median:.3f} | {pv} | {sec} | {binary} | {integ} |"
        )
    return "\n".join(lines) + "\n"
