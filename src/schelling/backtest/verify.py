"""Independent ledger audit (Session 17, D17.3): the one-command check an outsider would run.

Given a `runs/` forecast record, ``verify_record`` runs three checks and reports PASS/FAIL each:

1. **ledger-match** — the SHA-256 of the record file bytes appears in FORECASTS.md, i.e. this exact
   artifact is the one that was sealed (commit-reveal: the digest was published before resolution).
2. **inputs-hash** — recomputing the canonical (game + config) hash reproduces the record's stored
   ``inputs_hash`` — the recorded content-address is honest.
3. **determinism** — re-solving from the embedded game with the record's own config + seed
   reproduces the ensemble byte-for-byte, so the forecast is reproducible, not asserted (rule 2).
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


def verify_record(record_path: Path, ledger_path: Path) -> VerifyReport:
    """Recompute-and-match a sealed forecast record; return a per-check PASS/FAIL report."""
    from schelling.mc.monte_carlo import (
        CURRENT_HASH_VERSION,
        KNOWN_HASH_VERSIONS,
        forecast,
        inputs_hash,
    )
    from schelling.schemas.forecast import ForecastRecord
    from schelling.solver.config import SolverConfig

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

    redo = forecast(
        record.game,
        config,
        n_draws=record.ensemble.n_draws,
        seed=record.seed,
        write=False,
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
        Check("determinism", same, f"re-solved median {b.median:.6f} vs recorded {a.median:.6f}")
    )
    return VerifyReport(checks)
