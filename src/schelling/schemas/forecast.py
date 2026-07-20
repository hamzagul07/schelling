"""Solver-output and audit data contracts (BUILD_PLAN §3).

``ForecastRecord`` is the product's spine: designed as if a journalist will read it,
because one will. Every solve — even a unit-test solve — emits a complete record.

Session 1 defines the shapes and populates only the fields the vote layer produces
(``weighted_mean``, ``weighted_median``). Fields owned by later milestones — the per-round
octant matrix, offers, sensitivity table, outcome distribution — are typed here and left to
be filled in Sessions 2-3. See DECISIONS.md.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StoppingRule(StrEnum):
    """Which convergence rule ended a run (BUILD_PLAN §4 step 8, our upgrade)."""

    CONVERGED = "converged"  # forecast median moved < 0.5 units for 2 consecutive rounds
    ROUND_CAP = "round_cap"  # hard cap of 20 rounds hit


class RoundLog(BaseModel):
    """One round's full state — the audit trail Scholz say the original model lacked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    round_index: int = Field(ge=0)
    positions: dict[str, float]
    weighted_mean: float
    weighted_median: float
    # Populated from Session 2 onward; empty in the vote-only Session 1 pipeline.
    offers: list[dict[str, float]] = Field(default_factory=list)
    octant_matrix: dict[str, dict[str, str]] = Field(default_factory=dict)


class SolverResult(BaseModel):
    """One deterministic run of the solver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rounds: list[RoundLog]
    rounds_executed: int = Field(ge=0)
    stopping_rule: StoppingRule
    forecast_median: float
    forecast_mean: float


class SensitivityEntry(BaseModel):
    """One row of the one-at-a-time tornado (BUILD_PLAN §6).

    A single actor-field is moved to its ``low`` and then its ``high`` (all else at ``mode``);
    ``swing`` is the signed change in the forecast median. Rows are ranked by ``|swing|``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter: str  # human label, e.g. "france.position"
    actor_id: str
    field: str  # "position" | "salience" | "capability"
    low_value: float
    high_value: float
    forecast_at_low: float
    forecast_at_high: float
    swing: float  # forecast_at_high - forecast_at_low


class ForecastRecord(BaseModel):
    """The audit artifact — one for every solve, deterministic under ``seed``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    run_id: str
    engine_version: str  # git SHA of the engine that produced this record
    inputs_hash: str  # SHA-256 of the canonical (GameSpec + SolverConfig) JSON
    seed: int  # Monte Carlo master seed
    n_draws: int = 1
    solver_config: dict[str, str | float | int | bool] = Field(default_factory=dict)
    created_at: str | None = None  # ISO-8601; outside hashed content; None keeps runs identical

    forecast_median: float
    forecast_mean: float

    outcome_distribution: list[float] = Field(default_factory=list)
    ci80: tuple[float, float] | None = None
    settlement_point: float | None = None
    convergence_stats: dict[str, float] = Field(default_factory=dict)
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)
