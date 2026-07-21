"""The forecast ledger (Session 10, D10.6): sealed, pre-registered predictions for grading later.

A ledger entry commits, for one sealed question, each model's forecast (challenge and compromise)
to a hash *before* the event resolves. The commitment hashes the substantive prediction only —
question, model, inputs hash, seed, and ensemble statistics — deliberately excluding the engine git
SHA and timestamps, so the same inputs + seed reproduce the same commitment across engine commits.
The sealed game inputs stay out of the public tree; only the forecasts and hashes are recorded.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from schelling.schemas.forecast import ForecastRecord


def forecast_commitment(record: ForecastRecord) -> str:
    """A stable SHA-256 commitment to a forecast (excludes engine SHA / timestamps, D10.6)."""
    e = record.ensemble
    payload = {
        "question_id": record.question_id,
        "model": record.model,
        "inputs_hash": record.inputs_hash,
        "seed": record.seed,
        "ensemble": {
            "median": e.median,
            "mean": e.mean,
            "p10": e.p10,
            "p90": e.p90,
            "n_draws": e.n_draws,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row(record: ForecastRecord) -> str:
    e = record.ensemble
    return (
        f"| {record.model} | {e.median:.3f} | [{e.p10:.2f}, {e.p90:.2f}] | "
        f"`{record.inputs_hash[:12]}` | `{forecast_commitment(record)[:16]}` |"
    )


def ledger_entry(
    records: list[ForecastRecord], *, continuum: str, grade_date: str, note: str
) -> str:
    """Render one ledger entry (a question, its models' sealed forecasts, and the grading date)."""
    if not records:
        raise ValueError("a ledger entry needs at least one forecast record")
    qid = records[0].question_id
    frozen = records[0].game.frozen_at if records[0].game else "—"
    lines = [
        f"## {qid}",
        "",
        f"- **Frozen:** {frozen}  ·  **Grade on:** {grade_date}",
        f"- **Continuum:** {continuum}",
        f"- **Note:** {note}",
        "",
        "| Model | Forecast (median) | CI80 | inputs_hash | commitment |",
        "|---|---:|---|---|---|",
        *[_row(r) for r in records],
        "",
        "The commitment hash seals each forecast independent of engine version; re-running the "
        "sealed game with the same seed reproduces it. The outcome will be scored as "
        "|forecast - actual| on the same 0-100 continuum.",
        "",
    ]
    return "\n".join(lines)


_HEADER = """# FORECASTS.md — the sealed forecast ledger

Pre-registered predictions on real, unresolved events, sealed before the outcome is known and
graded afterward. Each question is forecast by **both** models — the challenge (BDM bargaining)
solver and the compromise (capability x salience weighted mean) model — so the DEU-backtest verdict
(the compromise model wins) is put to a live, out-of-sample test. Inputs are frozen and their hash
is recorded; the sealed game files themselves stay out of the public tree.
"""


def new_ledger(entry: str) -> str:
    """A fresh ledger document (header + first entry)."""
    return _HEADER + "\n" + entry


def append_entry(existing: str, entry: str) -> str:
    """Append an entry to an existing ledger document."""
    return existing.rstrip() + "\n\n" + entry


# ------------------------------------------------------------------------------------------------
# SHA-256-of-record ledger (Session 12, D12.0). Supersedes the partial ``forecast_commitment``:
# a sealed line pins the EXACT ``runs/`` record file by the SHA-256 of its bytes, so a reader can
# ``sha256sum runs/<file>`` and verify. ``schelling seal`` appends one line per record, idempotent.
LEDGER_START = "<!-- LEDGER:START -->"
LEDGER_END = "<!-- LEDGER:END -->"
_TABLE_HEAD = (
    "| model | vintage | question | frozen_at | median | sha256 (of the runs/ record file) |\n"
    "|---|---|---|---|---:|---|"
)


def record_sha256(path: Path) -> str:
    """SHA-256 of a forecast record file's bytes — the seal that pins that exact artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_row(
    *, model: str, vintage: str, question_id: str, frozen_at: str, median: float, sha: str
) -> str:
    """One ledger line (markdown table row) for a sealed record."""
    return f"| {model} | {vintage} | {question_id} | {frozen_at} | {median:.3f} | `{sha}` |"


def insert_seal_row(existing: str, row: str, sha: str) -> tuple[str, bool]:
    """Insert ``row`` into the ledger table before ``LEDGER_END``; idempotent on ``sha``.

    Returns ``(text, changed)``. If ``sha`` already appears anywhere in the document, nothing
    changes (``changed`` is False). If the marker block is missing, one is created.
    """
    if sha in existing:
        return existing, False
    if LEDGER_END in existing:
        return existing.replace(LEDGER_END, f"{row}\n{LEDGER_END}", 1), True
    block = f"{LEDGER_START}\n{_TABLE_HEAD}\n{row}\n{LEDGER_END}\n"
    return existing.rstrip() + "\n\n" + block, True


def empty_seal_ledger(header: str) -> str:
    """A fresh SHA-256 ledger: ``header`` prose + an empty marker-bounded table for ``seal``."""
    return f"{header.rstrip()}\n\n{LEDGER_START}\n{_TABLE_HEAD}\n{LEDGER_END}\n"


# ------------------------------------------------------------------------------------------------
# External anchoring via OpenTimestamps (Session 17, D17.2). On every seal we timestamp the ledger
# file with the `ots` client, proving the commitment existed at a Bitcoin-anchored time — anchoring
# that no one, including us, can backdate. Graceful no-op (a warning) when `ots` is not installed.
def stamp_ledger(ledger_path: Path, proofs_dir: Path) -> tuple[str | None, str]:
    """Timestamp ``ledger_path`` with OpenTimestamps; store the proof in ``proofs_dir``.

    Returns ``(proof_path | None, message)``. The proof is content-addressed by the ledger's
    SHA-256, so each distinct ledger state gets exactly one proof and re-stamping is idempotent.
    Missing `ots` tool or any failure is a soft no-op — never blocks a seal.
    """
    if not ledger_path.exists():
        return None, f"no ledger at {ledger_path} to timestamp"
    fsha = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    proof_dest = proofs_dir / f"{ledger_path.name}-{fsha[:12]}.ots"
    if proof_dest.exists():
        return str(proof_dest), f"already timestamped (proof {proof_dest})"
    try:
        result = subprocess.run(
            ["ots", "stamp", str(ledger_path)], capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError:
        return None, (
            "OpenTimestamps client not found — external anchoring skipped. "
            "Install it (`pip install opentimestamps-client`) and re-run `schelling seal`."
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"ots stamp failed ({exc}); external anchoring skipped"
    created = Path(str(ledger_path) + ".ots")
    if result.returncode != 0 or not created.exists():
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        return None, f"ots stamp produced no proof ({detail[-1] if detail else 'unknown'}); skipped"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    created.replace(proof_dest)
    return str(
        proof_dest
    ), f"timestamped {ledger_path.name} → {proof_dest} (verify with `ots verify`)"
