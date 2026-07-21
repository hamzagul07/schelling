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

from schelling.schemas.question import GameSpec


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


class Assumption(BaseModel):
    """Something a formalized draft asserted that the supplied text/sources do NOT establish.

    Defined here (a core data contract) so the ``ForecastRecord`` can carry a draft's assumptions
    end-to-end; the formalizer re-exports it. See D6.8.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement: str
    why: str  # why it had to be assumed (what evidence was missing)


class DraftMetadata(BaseModel):
    """Provenance for one formalize call — model, token usage, cost, retries.

    Carried into the ``ForecastRecord`` as ``formalizer_metadata`` so the provenance chain runs
    from formalization through the forecast (D6.8).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    retries: int  # schema-validation retries
    leak_retries: int = 0  # firewall rephrase retries (D6.5)
    created_at: str | None = None  # ISO-8601; left None keeps drafts reproducible in tests


class Ensemble(BaseModel):
    """Ensemble statistics over the per-draw converged **median** (the headline forecast).

    A dedicated block so that no field called ``median``/``mean`` changes meaning by layer
    (D4.2): ``SolverResult.forecast_median``/``forecast_mean`` describe one deterministic run;
    ``Ensemble.median``/``mean`` describe the distribution across Monte Carlo draws.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    median: float  # median of the outcome distribution (central estimate)
    mean: float  # mean of the outcome distribution (expected outcome / settlement point)
    p10: float  # 10th percentile (CI80 lower bound)
    p90: float  # 90th percentile (CI80 upper bound)
    n_draws: int


class ForecastRecord(BaseModel):
    """The audit artifact — one per Monte Carlo run, deterministic under ``seed``.

    The record is fully recomputable from ``(inputs_hash, solver_config, seed,
    engine_version)``; ``outcome_distribution`` embeds the raw draws as a convenience cache,
    not the source of truth (D4.1).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    run_id: str
    engine_version: str  # git SHA of the engine that produced this record
    inputs_hash: str  # SHA-256 of the canonical (GameSpec + SolverConfig) JSON
    seed: int  # Monte Carlo master seed
    solver_config: dict[str, str | float | int | bool] = Field(default_factory=dict)
    created_at: str | None = None  # ISO-8601; outside hashed content; None keeps runs identical

    ensemble: Ensemble

    # The input game (ranges intact) and the deterministic mode-game median trajectory, embedded
    # so a ForecastRecord report is fully self-describing — actor map, inputs table, and per-round
    # trajectory need no re-solve (D6.1). ``game`` is None on legacy records.
    game: GameSpec | None = None
    median_trajectory: list[float] = Field(default_factory=list)

    # Formalizer provenance, carried through when solving a DraftGameSpec (D6.8): the draft's
    # open assumptions and its formalize-call metadata. Empty/None when solving a bare GameSpec.
    assumptions: list[Assumption] = Field(default_factory=list)
    formalizer_metadata: DraftMetadata | None = None

    outcome_distribution: list[float] = Field(default_factory=list)  # raw draws (cache, D4.1)
    convergence_stats: dict[str, float] = Field(default_factory=dict)
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)
