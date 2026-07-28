"""Elicitation-ensemble data contracts (Session 45, D45).

When a situation is formalized several times independently, the drafts disagree — on which actors
are present and on where each actor's position, salience, and capability sit. These schemas record
that disagreement so it can be measured rather than assumed away: a per-actor agreement table (how
many drafts contained the actor, and the spread of each coordinate across drafts), the three-way
variance decomposition, and the summary a solved consensus game carries so its report can disclose
the elicitation uncertainty it now measures.

All are pure metadata. Like the rest of the ``ForecastRecord`` provenance they ride *outside*
``inputs_hash`` (which hashes game + config only), so attaching an :class:`ElicitationSummary` never
moves a sealed content-address.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CoordinateAgreement(BaseModel):
    """One coordinate's spread across the drafts that named this actor, and its consensus range."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str  # "position" | "salience" | "capability"
    draft_modes: list[float]  # the mode each draft stated (only drafts where the actor is present)
    mode_spread: float  # max(draft_modes) - min(draft_modes) — the elicitation disagreement
    consensus_low: float  # widened to span every draft's range (never narrower than any draft's)
    consensus_mode: float  # the median of the drafts' modes
    consensus_high: float


class ActorAgreement(BaseModel):
    """How much the drafts agreed about one actor: presence (k of N) and per-coordinate spread."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str
    name: str
    present_in: int  # k — number of drafts that named this actor
    n_drafts: int  # N
    low_presence: bool  # named by a minority of drafts (k * 2 < N) — retained and flagged
    coordinates: list[CoordinateAgreement]


class VarianceShares(BaseModel):
    """The three-way decomposition of total forecast variance into shares that sum to 1 (D45.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    elicitation: float  # share from choosing among drafts (across-draft variance)
    input_ranges: float  # share from the triangular input ranges within a draft (Monte Carlo)
    model_choice: float  # share from choosing among solvers
    total_variance: float  # the total forecast variance the shares divide
    method: str = ""  # one-line statement of how the decomposition was computed


class ElicitationSummary(BaseModel):
    """What a consensus game's report needs to disclose the elicitation uncertainty it measures.

    ``draft_hashes`` is the ensemble's commitment (D45.5): the SHA-256 of each draft file. The
    drafts are non-deterministic by nature, so the reproducible commitment is the set of their
    hashes together with the consensus game's own ``inputs_hash``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_drafts: int
    draft_hashes: list[str] = Field(default_factory=list)
    actors: list[ActorAgreement] = Field(default_factory=list)
    variance: VarianceShares | None = None  # attached by ``schelling variance`` when computed
