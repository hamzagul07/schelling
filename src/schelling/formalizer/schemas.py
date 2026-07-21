"""Data contracts for the formalizer (Phase 1).

A ``DraftGameSpec`` wraps a solver-ready :class:`GameSpec` with the extra material a human
reviewer needs before trusting it: an explicit ``assumptions`` list (anything asserted without
evidence), a template classification citing the concept library as *conceptual grounding only*,
and provenance metadata (model, token usage, cost). The LLM structures; nothing here produces a
probability (CLAUDE.md rule 1), and every real-world claim must trace to the supplied situation
text or sources (CLAUDE.md rule 6).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schelling.schemas.question import GameSpec


class Assumption(BaseModel):
    """Something the draft asserts that is NOT backed by the supplied text/sources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement: str
    why: str  # why it had to be assumed (what evidence was missing)


class TemplateClassification(BaseModel):
    """Which game template applies, grounded in the concept library (conceptual only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template: str
    rationale: str
    template_cards: list[str] = Field(default_factory=list)  # cited card names
    index_chunks: list[str] = Field(default_factory=list)  # cited lecture refs (concepts only)


class DraftExtraction(BaseModel):
    """Exactly what the LLM returns: the game plus assumptions and template classification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    game: GameSpec
    assumptions: list[Assumption]
    template_classification: TemplateClassification


class DraftMetadata(BaseModel):
    """Provenance for one formalize call — model, token usage, cost, retries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    retries: int  # schema-validation retries
    leak_retries: int = 0  # firewall rephrase retries (D6.5)
    created_at: str | None = None  # ISO-8601; left None keeps drafts reproducible in tests


class DraftGameSpec(BaseModel):
    """A reviewer-facing draft: the formalized game, its assumptions, and its provenance.

    Never auto-solved — editing the JSON and running ``schelling solve`` is the only path to a
    forecast (human in the loop by construction).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    game: GameSpec
    assumptions: list[Assumption]
    template_classification: TemplateClassification
    metadata: DraftMetadata
