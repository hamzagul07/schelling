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
    cost_usd: float  # total: token cost + web-search cost (D8.1)
    retries: int  # schema-validation retries
    leak_retries: int = 0  # firewall rephrase retries (D6.5)
    searches_used: int = 0  # server-side web searches performed (D8.1)
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
    # Which forecasting model produced the ensemble (Session 10, D10.5): "challenge" (the BDM
    # bargaining solver) or "compromise" (the capability x salience weighted mean). Default keeps
    # legacy records — which are all challenge-model — valid.
    model: str = "challenge"
    solver_config: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
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
    # True when the source draft was grounded on a live web search (carried from the draft, D9.0a):
    # the report then prints a caveat that the inputs rest on a live search, not a frozen snapshot.
    live_searched: bool = False
    # Optional ICB base-rate panel (Session 11, D11.2): historical outcome frequencies for
    # structurally similar crises. Off by default; never blended into the solver line.
    analog_panel: AnalogPanel | None = None

    outcome_distribution: list[float] = Field(default_factory=list)  # raw draws (cache, D4.1)
    convergence_stats: dict[str, float] = Field(default_factory=dict)
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)


class AnalogExample(BaseModel):
    """One historical ICB crisis-actor shown alongside the base-rate panel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    crisname: str
    year: int
    actor: str
    outcome: str


class AnalogPanel(BaseModel):
    """A base-rate panel from the ICB analog layer (Session 11, D11.2).

    Historical outcome frequencies among the N structurally most similar crises. It is a base rate,
    NOT a forecast: ``blend_weight`` is disclosed and defaults to 0 — the distribution is never
    mixed into the deterministic solver settlement line. Rendered as a clearly separated panel.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    n: int
    query: dict[str, float]  # the structural tags used (gravity, violence, n_actors)
    outcome_distribution: dict[str, float]  # outcome label -> fraction, most frequent first
    examples: list[AnalogExample] = Field(default_factory=list)
    blend_weight: float = 0.0  # disclosed: base rate is NOT blended into the solver forecast


# Printed on every advise output (CLI + report): advise mode is a one-sided lever search.
ADVISE_CAVEAT = (
    "One-sided search: opponents are held to the model's fixed behavior; real adversaries "
    "adapt. Treat as lever-finding, not a playbook."
)

# Equilibrium mode drops the one-sided caveat for this stronger one (Session 21, Advise 2.0).
SUCCESSOR_CAVEAT = (
    "Equilibrium mode assumes model-optimal play by all actors — an upper bound on adaptation, "
    "not a prophecy."
)


class MoveAction(BaseModel):
    """A named diplomatic action from the move vocabulary (moves.yaml), with its parameter delta."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str  # e.g. "phased_concession", "coalition_pull"
    rationale: str
    delta: str  # human-readable typed delta, e.g. "position -10 (toward the settlement)"


class ResponsePreview(BaseModel):
    """One-ply preview (Advise 2.0): the most-affected opponent's best single counter-response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    responder_id: str
    responder_move: str  # e.g. "position -> 45"
    gross_benefit: float  # the advisor's benefit before any response
    net_benefit: float  # the advisor's benefit after the responder's best counter
    simulated: bool = False  # True = challenge lens, computed at reduced draws (labeled)


class Robustness(BaseModel):
    """Robustness grade of a move's benefit across the MC draws (Advise 2.0)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benefit_ci_lo: float  # 10th percentile of the per-draw benefit
    benefit_ci_hi: float  # 90th percentile
    sign_stable_fraction: float  # fraction of draws whose benefit shares the point-benefit sign
    grade: str  # "ROBUST" (>= 90% sign-stable) | "KNIFE-EDGE"


class OwnMove(BaseModel):
    """One candidate move the advising actor could make (Session 7 advise mode).

    ``benefit`` and ``cost`` are reported separately and never combined into one score: benefit
    is how much closer to the actor's ideal the settlement lands; cost is the position distance
    the actor concedes to get there (0 for a salience move).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: str  # "position" | "salience"
    value: float
    settlement_median: float
    benefit: float  # |median_before - ideal| - |median_after - ideal|
    cost: float  # position distance conceded from the actor's ideal (0 for salience)
    beyond_stated_range: bool
    # Advise 2.0 enrichments (optional, defaulted so Session-7/12 records stay valid).
    action: MoveAction | None = None  # the vocabulary action, when the move came from moves.yaml
    response: ResponsePreview | None = None  # one-ply best-response preview (top moves only)
    robustness: Robustness | None = None  # benefit CI + sign-stability grade


class PersuasionTarget(BaseModel):
    """A feasible shift of ANOTHER actor toward the advisor's ideal — the "who to work on" list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str
    dimension: str  # "position" | "salience"
    from_value: float
    to_value: float
    settlement_median: float
    benefit: float  # settlement shift toward the advisor's ideal
    # "energize" (raise salience / pull position toward the advisor) vs "defuse" (lower salience)
    kind: str = "energize"
    action: MoveAction | None = None  # the vocabulary action, when applicable (Advise 2.0)
    robustness: Robustness | None = None


class EquilibriumMove(BaseModel):
    """One actor's move at the equilibrium fixed point (Advise 2.0, --mode equilibrium)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str
    position_from: float
    position_to: float
    salience_from: float
    salience_to: float


class EquilibriumResult(BaseModel):
    """Iterated best-response equilibrium under the exact lens (Advise 2.0)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    settlement: float  # the settled settlement (last on the path)
    converged: bool
    iterations: int
    path: list[float] = Field(default_factory=list)  # settlement after each round
    cycle: list[float] = Field(default_factory=list)  # non-empty when a cycle is detected
    moves: list[EquilibriumMove] = Field(default_factory=list)


class MovePackage(BaseModel):
    """A best two-move bundle under the exact lens (Advise 2.0), benefit/cost separated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    moves: list[str]  # the two move descriptions (own and/or persuasion)
    settlement_median: float
    benefit: float
    cost: float
    robustness: Robustness | None = None


class AdviseLens(BaseModel):
    """One advice lens (Session 12, D12.4): a full lever search under a single model.

    ``exact`` marks the compromise (weighted-mean) lens, whose settlement shifts are closed-form —
    each actor's marginal effect is its weight share — as opposed to the challenge lens, whose
    settlements come from a Monte-Carlo simulated search.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str  # "challenge" | "compromise"
    exact: bool  # True = closed-form (compromise); False = simulated (challenge)
    baseline_median: float
    own_moves: list[OwnMove] = Field(default_factory=list)
    top_moves: list[OwnMove] = Field(default_factory=list)
    persuasion_targets: list[PersuasionTarget] = Field(default_factory=list)
    # Advise 2.0 (optional): equilibrium fixed point (exact lens) and best two-move packages.
    equilibrium: EquilibriumResult | None = None
    packages: list[MovePackage] = Field(default_factory=list)


class AdviseRecord(BaseModel):
    """The advise-mode audit artifact — deterministic under ``seed`` like everything else.

    A one-sided lever search from the advising actor's viewpoint: own moves (position/salience
    sweeps) and persuasion targets (feasible shifts of other actors), each solved with the same
    derived seeds for comparability. Not a playbook — opponents are held to the model's fixed
    behaviour (see the standing caveat rendered on every advise report).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    run_id: str
    engine_version: str
    inputs_hash: str  # SHA-256 of canonical (game + solver_config + advise_config + actor)
    seed: int
    created_at: str | None = None

    advising_actor: str
    ideal: float  # the advisor's mode position before any move
    baseline_median: float  # settlement with the game as-is (target_draws)
    baseline_run_id: str  # the baseline ForecastRecord reference

    advise_config: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    solver_config: dict[str, str | float | int | bool | None] = Field(default_factory=dict)

    own_moves: list[OwnMove] = Field(default_factory=list)
    top_moves: list[OwnMove] = Field(default_factory=list)  # re-solved at target_draws
    persuasion_targets: list[PersuasionTarget] = Field(default_factory=list)  # ranked

    # Which model the primary (top-level) lever tables came from, and whether they are closed-form
    # (D12.4). ``second_lens`` carries the other model's lens when ``--solver both`` — e.g. the
    # exact compromise lens alongside the simulated challenge lens, rendered side by side.
    model: str = "challenge"
    exact: bool = False
    second_lens: AdviseLens | None = None

    # Advise 2.0 (optional, defaulted): the run mode and a deterministic strategy-brief paragraph,
    # plus equilibrium/packages carried on the primary lens fields for the report.
    mode: str = "levers"  # "levers" (default) | "equilibrium"
    strategy_brief: str = ""
    equilibrium: EquilibriumResult | None = None
    packages: list[MovePackage] = Field(default_factory=list)

    game: GameSpec | None = None  # for the report's baseline actor map
