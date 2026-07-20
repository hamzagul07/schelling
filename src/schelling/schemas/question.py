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


class GameSpec(BaseModel):
    """One formalized situation — the deterministic solver's input.

    The canonical JSON serialization of this object is what gets SHA-256'd into a
    ``ForecastRecord.inputs_hash``; keep it stable and order-independent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    frozen_at: str
    continuum: Continuum
    actors: list[Actor] = Field(min_length=1)
    template: str
    horizon: str
    notes: str = ""
