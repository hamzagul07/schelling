"""Game / question data contract (BUILD_PLAN §3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schelling.schemas.stakeholders import Actor


class Continuum(BaseModel):
    """The one-dimensional issue continuum a game is decomposed onto.

    ``anchor_0`` and ``anchor_100`` describe the two ends of the 0-100 policy scale in
    natural language, so a reader can interpret a numeric forecast.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    anchor_0: str
    anchor_100: str


class RubricBand(BaseModel):
    """One band of a banded resolution rubric: an inclusive ``[lo, hi]`` slice of the 0-100
    continuum with the outcome it denotes, in the rubric's own words (Session 22, D22.2).

    Bands tile the continuum. Membership at report time uses the band's ``lo`` as a threshold (a
    draw falls in the last band whose ``lo`` it clears), so float draws partition cleanly even
    where the written ``hi``/``lo`` integers leave unit gaps.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    lo: float  # inclusive lower bound on the 0-100 continuum
    hi: float  # inclusive upper bound
    label: str  # what this band means, verbatim from the rubric


class ResolutionRubric(BaseModel):
    """How a sealed forecast will be graded once its real-world event resolves (Session 17, D17.1).

    Written *before* resolution and pinned inside the sealed game so grading cannot be reverse-fit
    to the outcome. It is grading metadata, not a solver input: it is **excluded** from the
    ``inputs_hash`` (see ``mc.monte_carlo.inputs_hash``), so it never changes a forecast or the
    content-address of a run.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolution_criteria: str  # the binary yes/no event that counts as the question resolving
    adjudicating_sources: list[str] = Field(min_length=1)  # authoritative sources consulted
    outcome_mapping: str  # rule mapping the real-world outcome onto the 0-100 settlement continuum
    grading_formula: str  # e.g. "score = |forecast_median - actual| on the 0-100 continuum"
    # Optional structured bands (D22.2): when present the report maps the MC draws through them for
    # per-band probabilities; when absent the rubric is treated as arithmetic/linear (the grading
    # formula maps the outcome onto the continuum directly). Excluded from the hash with the rubric.
    bands: list[RubricBand] = Field(default_factory=list)
    # Which scoring rule is authoritative (Session 40, D40.1). A proper scoring rule reads the whole
    # forecast distribution, not just the median; the template now declares one primary and keeps
    # |median - actual| as an explicit secondary. Both fields are grading metadata — like the rest
    # of the rubric they are EXCLUDED from ``inputs_hash``, so declaring them cannot move a sealed
    # number. Empty ``primary_metric`` means the legacy default ``absolute_error`` (see scoring);
    # every question sealed before D40 declared |median - actual| and keeps it untouched.
    primary_metric: str = ""  # "" -> absolute_error; else "brier" (banded) or "crps" (arithmetic)
    secondary_metrics: list[str] = Field(default_factory=list)  # reported alongside, labelled


class GameSpec(BaseModel):
    """One formalized situation — the deterministic solver's input.

    The canonical JSON serialization of this object is what gets SHA-256'd into a
    ``ForecastRecord.inputs_hash``; keep it stable and order-independent. ``resolution_rubric`` is
    the one exception — it is grading metadata and is excluded from the hash (D17.1).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    frozen_at: str
    continuum: Continuum
    actors: list[Actor] = Field(min_length=1)
    template: str
    horizon: str
    notes: str = ""
    resolution_rubric: ResolutionRubric | None = None
    # Report-display coding (Session 23, D23.2): actor ids that are non-voting / out-of-body
    # influence (e.g. the subject of a committee's decision). Presentation metadata only — like the
    # rubric it is EXCLUDED from ``inputs_hash``, so it never changes a forecast or a sealed hash.
    non_voting_actor_ids: list[str] = Field(default_factory=list)
    # Optional per-actor short display names, keyed by actor id (Session 25, D25.3). Used by the
    # report prose and figures; the stakeholder table keeps the full name. Absent ids fall back to
    # the first clause of the actor's name. Display metadata only — also EXCLUDED from the hash.
    short_names: dict[str, str] = Field(default_factory=dict)
