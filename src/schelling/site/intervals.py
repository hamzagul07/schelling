"""The committed snapshot of the sealed forecasts' 80% intervals (Session 34, D34.1).

The hero figure plots each forecast's 80% interval (p10, p90). Those live in the ``runs/`` record
files, which are gitignored (commit-reveal) and therefore absent on CI — so a figure that read them
directly could never survive ``site build --check``. Instead the intervals are snapshotted into a
committed file, ``FORECAST-INTERVALS.json``, keyed by the ledger SHA-256. ``site build`` reads only
that committed snapshot (a pure function of committed files); ``site build --refresh-intervals``
regenerates it from the records when they are present locally. The medians remain governed by
``FORECASTS.md``; this file adds only the interval endpoints, which are part of the already-sealed
record (disclosing them early strengthens the commitment, and a stale snapshot is caught by
``test_intervals_match_records`` where the records are present).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from schelling.site.data import LedgerRow, _parse_ledger

INTERVALS_FILE = "FORECAST-INTERVALS.json"
_NOTE = (
    "Display snapshot of the 80% intervals (p10, p90) of the sealed forecasts, keyed by the ledger "
    "SHA-256. Regenerated from the sealed run records by `schelling site build "
    "--refresh-intervals`; the records stay gitignored (commit-reveal). Medians are governed by "
    "FORECASTS.md; this file adds only the interval endpoints of the already-sealed records."
)


def load_intervals(repo_root: Path) -> dict[str, tuple[float, float]]:
    """Read the committed interval snapshot as ``{sha256: (p10, p90)}`` (empty if absent)."""
    path = repo_root / INTERVALS_FILE
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    out: dict[str, tuple[float, float]] = {}
    for sha, iv in raw.get("intervals", {}).items():
        out[sha] = (float(iv["p10"]), float(iv["p90"]))
    return out


def compute_intervals(repo_root: Path, ledger: list[LedgerRow]) -> dict[str, tuple[float, float]]:
    """Match each ledger row to its ``runs/`` record by SHA-256 and read its 80% interval. Requires
    the records to be present (local only); rows without a matching record are omitted."""
    runs = repo_root / "runs"
    if not runs.exists():
        return {}
    by_sha: dict[str, Path] = {}
    for path in sorted(runs.glob("*.json")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        by_sha[digest] = path
    out: dict[str, tuple[float, float]] = {}
    for row in ledger:
        rec = by_sha.get(row.sha256)
        if rec is None:
            continue
        ensemble = json.loads(rec.read_text()).get("ensemble", {})
        p10, p90 = ensemble.get("p10"), ensemble.get("p90")
        if isinstance(p10, int | float) and isinstance(p90, int | float):
            out[row.sha256] = (round(float(p10), 3), round(float(p90), 3))
    return out


def refresh_intervals(repo_root: Path) -> tuple[int, int]:
    """Regenerate ``FORECAST-INTERVALS.json`` from the records. Returns ``(matched, total)`` ledger
    rows. Deterministic: keys sorted, endpoints rounded to 3 decimals."""
    ledger = _parse_ledger((repo_root / "FORECASTS.md").read_text())
    intervals = compute_intervals(repo_root, ledger)
    payload = {
        "_note": _NOTE,
        "intervals": {
            sha: {"p10": intervals[sha][0], "p90": intervals[sha][1]} for sha in sorted(intervals)
        },
    }
    (repo_root / INTERVALS_FILE).write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return len(intervals), len(ledger)
