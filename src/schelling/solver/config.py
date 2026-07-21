"""Solver configuration (deterministic; every stochastic path takes an explicit seed)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RangeMode(StrEnum):
    """How the continuum range ``R = x_max - x_min`` in the utility formulas is set.

    * ``DYNAMIC`` — Scholz's literal reading: ``max - min`` of the *current* round's positions,
      recomputed each round. Required for the BDM-1994 replication (positions are years 4-10).
    * ``FIXED`` — a fixed range (default 100), our documented upgrade for inputs already on a
      0-100 continuum (the Session-1 toy fixture and future live cases). See DECISIONS.md D1.2.
    """

    DYNAMIC = "dynamic"
    FIXED = "fixed"


class SolverConfig(BaseModel):
    """Deterministic solver settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    range_mode: RangeMode = RangeMode.DYNAMIC
    fixed_range: float = Field(default=100.0, gt=0.0)
    q: float = Field(default=1.0, ge=0.0, le=1.0)  # status-quo probability Q (Scholz: 1.0)
    apply_risk: bool = True  # run the second, risk-adjusted EU pass (Appendix steps 8-10)
    conflict_resolves: bool = False  # conflict (both EU>0) = "uncertain outcome" = no move (A4)
    security_mode: str = "adversary"  # "adversary" (col sum) or "own" (row sum) — A2
    # Status-quo reference point (Session 10, D10.4). When None, the status quo is "no move" (an
    # actor keeps its own position, u_sq at distance 0). When set to a continuum point, the
    # reversion outcome is that point, so an actor's status-quo utility falls with its distance
    # from it — the "status quo as an actual reference" variant. Only bites when Q < 1.
    reference_point: float | None = None
    max_rounds: int = Field(default=20, ge=1)  # hard cap (BUILD_PLAN §4 step 8)
    convergence_epsilon: float = 0.5  # median move < this for 2 rounds -> converged
    convergence_patience: int = Field(default=2, ge=1)
    seed: int = 0
