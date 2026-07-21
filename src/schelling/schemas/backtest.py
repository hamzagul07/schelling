"""Data contracts for the DEU backtest (BUILD_PLAN Phase 2, Session 9).

A ``DEUIssue`` is one controversial issue from the DEU dataset, normalized to a solver-ready
``GameSpec`` (point estimates) plus the *actual* decision outcome we score against. A
``BacktestRecord`` is the deterministic audit artifact of a whole harness run: per-method error
statistics over the full issue set, the worst issues for inspection, and the gate verdict.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schelling.schemas.question import GameSpec


class DEUIssue(BaseModel):
    """One DEU issue, normalized: the solver-ready game plus the actual outcome to score against.

    ``game`` carries the actors' positions and saliences as point estimates on the 0-100 policy
    scale; capability is a fixed constant (DEU records no capability — see D9.2). ``outcome`` is
    the actual decision outcome on the same 0-100 scale; ``reference_point`` is the DEU reference
    point (status quo) when recorded, else ``None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: str
    proposal_id: str
    proposal_name: str
    procedure: str  # "COD" (ordinary) | "CNS" (consultation)
    outcome: float
    reference_point: float | None
    game: GameSpec


class IssueError(BaseModel):
    """One issue's forecast vs. actual under one method — the row behind every MAE."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: str
    proposal_name: str
    forecast: float
    actual: float
    error: float  # |forecast - actual|


class MethodResult(BaseModel):
    """Error statistics for one forecasting method over the full issue set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str  # stable id, e.g. "solver_paper", "baseline_wmean"
    label: str  # human label
    kind: str  # "solver" | "baseline" | "sweep"
    config: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    mae: float  # mean absolute error (the headline)
    rmse: float
    median_error: float
    max_error: float
    errors: list[float] = Field(default_factory=list)  # per issue, in issue order (for the report)


class SplitSample(BaseModel):
    """A split-sample validation of a tuned model choice (Session 10, D10.4/item 4).

    Any model modification beyond restoring inputs is tuned on a training half and scored on a
    held-out test half, so an improvement can't be an artifact of tuning on the same data.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str  # what was tuned, e.g. "rp-anchored challenge: Q"
    tuned_param: str  # e.g. "q"
    candidates: list[float]  # the values swept on the train half
    selected: float  # the value that minimized train MAE
    train_n: int
    test_n: int
    train_mae: float  # tuned model, train half
    test_mae: float  # tuned model, test half (the honest number)
    test_baseline_mae: float  # the equally-equipped weighted mean on the test half
    passed: bool  # test_mae < test_baseline_mae (no overfit to the tuning half)


class OracleSummary(BaseModel):
    """DIAGNOSTIC noise-floor oracle (D11.0): a flexible CV model vs the compromise mean.

    ``oracle_mae`` is the cross-validated MAE of a deliberately flexible model (kernel/linear ridge
    over rich features incl. positions) — an estimate of the extractable-signal ceiling. A small (or
    negative) ``gap`` means the compromise mean is at/near that ceiling: no headroom to exploit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_issues: int
    folds: int
    best_model: str
    oracle_mae: float
    compromise_mae: float
    gap: float  # compromise_mae - oracle_mae; small/negative => mean at ceiling


class BacktestRecord(BaseModel):
    """The deterministic audit artifact of a backtest run (same inputs + seed -> byte-identical)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: str  # e.g. "DEU III (doi:10.34810/data53)"
    dataset_sha256: str  # SHA-256 of the source CSV — pins the exact data version
    n_issues: int
    seed: int
    draws: int  # nominal MC draws (point estimates -> degenerate; recorded for parity, D9.3)
    capability: float  # the fixed capability (equal mode), else 0.0 when sourced (D9.2/D10.1)
    engine_version: str
    created_at: str | None = None  # ISO-8601; None keeps runs byte-identical (rule 2)

    # Session-10 fair-fight context (defaults keep Session-9 records valid).
    capability_mode: str = "equal"  # "equal" (D9.2) or "sourced" (treaty regime, D10.1)
    reference_point_used: bool = False  # whether an rp-anchored challenge variant is included
    split_sample: SplitSample | None = None  # validation of the rp/Q tuning (item 4)
    oracle: OracleSummary | None = None  # noise-floor diagnostic (Session 11, D11.0)

    methods: list[MethodResult]
    primary_method: str  # the solver config the gate is judged on
    baseline_methods: list[str]  # the naive baselines the primary must beat
    gate_passed: bool  # primary MAE < every baseline MAE
    worst_issues: list[IssueError] = Field(default_factory=list)  # worst-N by the primary method
