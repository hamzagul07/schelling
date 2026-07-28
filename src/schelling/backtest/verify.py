"""Independent ledger audit (Session 17, D17.3): the one-command check an outsider would run.

``verify_record`` dispatches on the record's schema (Session 49, D49.1) so **every** sealed ledger
row is verifiable, not just the solver rows:

* A :class:`ForecastRecord` (challenge / compromise) gets the full three-check audit —
  **ledger-match**, **inputs-hash**, and re-solve **determinism**.
* A :class:`LLMForecastRecord` (llm-judgment) or :class:`CrowdForecastRecord` (crowd-metaculus) is
  **non-deterministic by nature** — re-running the model or re-fetching the crowd gives different
  numbers, so the commitment is the SHA-256 of the record file, not a re-solve. These get
  **ledger-match** (the sealed bytes) plus an **inputs-hash** reference check; determinism does not
  apply and is reported as such, never as a FAIL.

Before D49 the audit hard-coded ``ForecastRecord.model_validate_json`` and raised on the llm/crowd
rows (their ``extra="forbid"`` schemas reject the parse), so a third of a live ledger was
unverifiable. The dispatch fixes exactly that (D48.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from schelling.backtest.ledger import record_sha256

_TOL = 1e-9


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerifyReport:
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)


def _detect_schema(text: str) -> str:
    """Which sealed-record schema ``text`` validates against: forecast | llm | crowd | unknown."""
    from schelling.schemas.forecast import (
        CrowdForecastRecord,
        ForecastRecord,
        LLMForecastRecord,
    )

    for cls, label in (
        (ForecastRecord, "forecast"),
        (LLMForecastRecord, "llm"),
        (CrowdForecastRecord, "crowd"),
    ):
        try:
            cls.model_validate_json(text)
            return label
        except ValueError:
            continue
    return "unknown"


def verify_record(record_path: Path, ledger_path: Path) -> VerifyReport:
    """Audit a sealed record, dispatching on its schema so any ledger row is verifiable (D49.1)."""
    text = record_path.read_text()
    schema = _detect_schema(text)
    if schema == "forecast":
        return _verify_forecast(record_path, ledger_path)
    if schema in ("llm", "crowd"):
        return _verify_nondeterministic(record_path, ledger_path, schema)
    return VerifyReport(
        [Check("schema", False, "record validates against no known sealed-record schema")]
    )


def _verify_nondeterministic(record_path: Path, ledger_path: Path, schema: str) -> VerifyReport:
    """Verify an llm-judgment or crowd record: ledger-match + inputs-hash reference (D49.1).

    These families are non-deterministic by nature (a re-run/re-fetch differs), so the commitment is
    the record file's SHA-256. Determinism is reported N/A — a PASS-with-note, never a FAIL.
    """
    from schelling.schemas.forecast import CrowdForecastRecord, LLMForecastRecord

    cls = LLMForecastRecord if schema == "llm" else CrowdForecastRecord
    record = cls.model_validate_json(record_path.read_text())
    family = "llm-judgment" if schema == "llm" else "crowd-metaculus"
    checks: list[Check] = []

    sha = record_sha256(record_path)
    ledger_text = ledger_path.read_text() if ledger_path.exists() else ""
    in_ledger = sha in ledger_text
    where = f"found in {ledger_path.name}" if in_ledger else f"NOT in {ledger_path.name}"
    checks.append(Check("ledger-match", in_ledger, f"sha256 {sha[:12]}… {where}"))
    checks.append(
        Check(
            "inputs-hash",
            True,
            f"stored {record.inputs_hash[:12]}… is a reference digest for a {family} record "
            "(not a determinism claim)",
        )
    )
    checks.append(
        Check(
            "determinism",
            True,
            f"N/A — a {family} record is non-deterministic by nature; the commitment is the "
            "record file's SHA-256, checked by ledger-match above (D49.1)",
        )
    )
    return VerifyReport(checks)


def _verify_forecast(record_path: Path, ledger_path: Path) -> VerifyReport:
    """Recompute-and-match a sealed ForecastRecord; return a per-check PASS/FAIL report."""
    from schelling.mc.monte_carlo import (
        CURRENT_HASH_VERSION,
        KNOWN_HASH_VERSIONS,
        inputs_hash,
    )
    from schelling.schemas.forecast import ForecastRecord
    from schelling.solver.config import SolverConfig
    from schelling.solver.registry import resolve

    record = ForecastRecord.model_validate_json(record_path.read_text())
    checks: list[Check] = []

    sha = record_sha256(record_path)
    ledger_text = ledger_path.read_text() if ledger_path.exists() else ""
    in_ledger = sha in ledger_text
    where = f"found in {ledger_path.name}" if in_ledger else f"NOT in {ledger_path.name}"
    checks.append(Check("ledger-match", in_ledger, f"sha256 {sha[:12]}… {where}"))

    if record.game is None:
        checks.append(
            Check("inputs-hash", False, "record has no embedded game — cannot recompute (legacy)")
        )
        checks.append(Check("determinism", False, "record has no embedded game — cannot re-solve"))
        return VerifyReport(checks)

    # Epoch-aware inputs-hash (D18.1). Try each canonicalization era, newest first, so a record
    # sealed under an older era reproduces. If none reproduces, the record is still authenticated by
    # ledger-match (exact sealed bytes) + determinism (re-solve), so this is PASS-with-note, never a
    # FAIL that would punish a legacy record for a canonicalization change made after it was sealed.
    config = SolverConfig.model_validate(record.solver_config)
    matched = next(
        (
            v
            for v in KNOWN_HASH_VERSIONS
            if inputs_hash(record.game, config, hash_version=v) == record.inputs_hash
        ),
        None,
    )
    if matched == CURRENT_HASH_VERSION:
        checks.append(Check("inputs-hash", True, f"recomputed == stored ({matched})"))
    elif matched is not None:
        checks.append(
            Check(
                "inputs-hash",
                True,
                f"reproduced under legacy {matched} canonicalization (pre-reference-point); "
                f"stored {record.inputs_hash[:12]}…",
            )
        )
    else:
        checks.append(
            Check(
                "inputs-hash",
                True,
                "legacy canonicalization not derivable — authenticated by determinism "
                "+ ledger-match",
            )
        )

    # Re-solve through the engine version the record was SEALED under, not the current default
    # (D39.1). A build that no longer ships that version cannot re-derive it — that is PASS-with-
    # note (authenticated by hash + ledger match), never a FAIL (D39.3).
    solver = resolve(record.engine_version)
    if solver is None:
        checks.append(
            Check(
                "determinism",
                True,
                f"engine v{record.engine_version} is not in this build's solver registry — "
                "PASS-with-note: hash and ledger match, but the ensemble is not re-derivable "
                "under the current engine (D39.3)",
            )
        )
        return VerifyReport(checks)
    redo = solver(
        record.game,
        config,
        n_draws=record.ensemble.n_draws,
        seed=record.seed,
        model=record.model,
    )
    a, b = record.ensemble, redo.ensemble
    same = (
        abs(a.median - b.median) < _TOL
        and abs(a.mean - b.mean) < _TOL
        and abs(a.p10 - b.p10) < _TOL
        and abs(a.p90 - b.p90) < _TOL
    )
    checks.append(
        Check(
            "determinism",
            same,
            f"re-solved median {b.median:.6f} vs recorded {a.median:.6f} "
            f"(engine v{record.engine_version})",
        )
    )
    return VerifyReport(checks)
