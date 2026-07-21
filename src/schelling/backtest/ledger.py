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
