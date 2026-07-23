"""The precedents draft artifact (Session 29): the finder's output, ratified by a human (D29.2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schelling.schemas.forecast import Precedent


class PrecedentSet(BaseModel):
    """A precedents draft: the proposed prior comparable decisions for one question.

    Written by ``schelling precedents``; nothing is auto-accepted. A human ratifies by editing
    the file — setting ``ratified: true`` on accepted placements and quoting their ratification in
    ``ratification_note`` — before the set feeds the reference-class panel or the evidence river.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    precedents: list[Precedent] = Field(default_factory=list)
    source_model: str
    cost_usd: float = 0.0
    searches_used: int = 0
    created_at: str | None = None
    ratification_note: str = ""  # the human ratification, quoted (empty until ratified)
    # The reference class is sessions-AT-RISK (D30.1): identify the population of decision
    # opportunities first, then the outcomes. ``sessions_at_risk`` is the population size from
    # records (None = enumeration not fully sourced -> report INCOMPLETE, never a base rate).
    reference_class: str = ""  # the population definition + start date, as the model stated it
    sessions_at_risk: int | None = None  # the denominator
