"""Stakeholder data contract (BUILD_PLAN §3).

All three core values (position, salience, capability) live on a 0-100 scale, per the
original Policon input procedure: the strongest actor's capability = 100, others
proportional. The ``(low, mode, high)`` triangular ranges are our upgrade over Policon's
point estimates; a point estimate is simply ``low == mode == high``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TriangularEstimate(BaseModel):
    """A ``(low, mode, high)`` triangular range for one input value.

    A point estimate — the form used by the replication fixture — is the degenerate case
    ``low == mode == high``. Monte Carlo (BUILD_PLAN §6) draws from this triangle; the
    deterministic solver consumes the ``mode``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float
    mode: float
    high: float

    @model_validator(mode="after")
    def _ordered(self) -> TriangularEstimate:
        if not (self.low <= self.mode <= self.high):
            raise ValueError(
                f"triangular estimate must satisfy low <= mode <= high, "
                f"got low={self.low}, mode={self.mode}, high={self.high}"
            )
        return self

    @property
    def is_point(self) -> bool:
        """True when this is a degenerate point estimate (``low == mode == high``)."""
        return self.low == self.mode == self.high

    @classmethod
    def point(cls, value: float) -> TriangularEstimate:
        """Construct a point estimate ``low == mode == high == value``."""
        return cls(low=value, mode=value, high=value)


class Evidence(BaseModel):
    """A single sourced justification attached to an actor's inputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    date: str
    note: str


class Actor(BaseModel):
    """A stakeholder in one game.

    ``position``, ``salience`` and ``capability`` are triangular estimates on a 0-100 scale.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    position: TriangularEstimate
    salience: TriangularEstimate
    capability: TriangularEstimate
    evidence: list[Evidence] = Field(default_factory=list)
