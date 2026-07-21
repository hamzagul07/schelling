"""Data contracts for the formalizer (Phase 1).

A ``DraftGameSpec`` wraps a solver-ready :class:`GameSpec` with the extra material a human
reviewer needs before trusting it: an explicit ``assumptions`` list (anything asserted without
evidence), a template classification citing the concept library as *conceptual grounding only*,
and provenance metadata (model, token usage, cost). The LLM structures; nothing here produces a
probability (CLAUDE.md rule 1), and every real-world claim must trace to the supplied situation
text or sources (CLAUDE.md rule 6).

``Assumption`` and ``DraftMetadata`` are core data contracts (they also ride inside a
``ForecastRecord`` when solving a draft), so they live in ``schemas.forecast`` and are
re-exported here for convenience.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schelling.schemas.forecast import Assumption, DraftMetadata
from schelling.schemas.question import GameSpec

__all__ = [
    "Assumption",
    "DraftExtraction",
    "DraftGameSpec",
    "DraftMetadata",
    "TemplateClassification",
]


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
