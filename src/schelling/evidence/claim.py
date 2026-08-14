"""The evidence claim every structured source returns (Session 52, D52).

A retrieved series, event count, or session record is NEVER a coordinate. It is a *citable claim*:
a value (or a record) with the provider that served it, the provider's own identifier for it, and
the date it was retrieved. A human or the formalizer cites the claim when setting a coordinate;
nothing here writes one.

Two disciplines live here, both non-negotiable (item 4):

* **Provenance on every claim** — ``provider`` + ``identifier`` + ``retrieved_at`` are required, so
  no number can enter the pipeline without a source and a date.
* **Disagreement widens, never resolves** — :func:`widen_range` returns the *union* ``[min, max]``
  of the disagreeing values with every claim attached; it never averages them or picks a side.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class EvidenceClaim(BaseModel):
    """One sourced datum or record — a candidate citation, never an actor coordinate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str  # "dbnomics" | "ucdp" | "acled" | "iaea-archive" | ...
    identifier: str  # the provider's own id: series code, dataset id, event id, document url
    title: str  # human-readable description of what this is
    retrieved_at: str  # ISO date the claim was retrieved (supplied, never a wall clock)
    value: float | None = (
        None  # the number, when the claim is a datum; None for a record/enumeration
    )
    unit: str = ""
    period: str = ""  # the observation period / event date the value refers to
    url: str = ""  # a link a human can open to verify the claim
    note: str = ""

    def citation(self) -> str:
        """A one-line citation: provider:identifier = value (unit, period) retrieved YYYY-MM-DD."""
        head = f"{self.provider}:{self.identifier}"
        if self.value is not None:
            span = ", ".join(p for p in (self.unit, self.period) if p)
            head += f" = {self.value:g}" + (f" ({span})" if span else "")
        return f"{head} — retrieved {self.retrieved_at}"


class WidenedRange(BaseModel):
    """The union of disagreeing sourced values — the widened range, with its supporting claims."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lo: float
    hi: float
    claims: list[EvidenceClaim]

    @property
    def disagreement(self) -> float:
        return round(self.hi - self.lo, 6)

    def as_note(self) -> str:
        """Prose stating the widened range and every source it rests on (never a single point)."""
        srcs = "; ".join(c.citation() for c in self.claims)
        if self.lo == self.hi:
            return f"{self.lo:g} (agreed by {len(self.claims)} source(s)) — {srcs}"
        return (
            f"[{self.lo:g}, {self.hi:g}] — {len(self.claims)} sources disagree by "
            f"{self.disagreement:g}; the range is WIDENED to their union, "
            f"not resolved to one side. {srcs}"
        )


def widen_range(claims: Sequence[EvidenceClaim]) -> WidenedRange | None:
    """Combine numeric claims into the union of their values — disagreement WIDENS the range (D52).

    Returns ``None`` when no claim carries a value. When sources disagree the result spans
    ``[min, max]`` and keeps every claim; it never averages, weights, or selects a winner.
    """
    numeric = [c for c in claims if c.value is not None]
    if not numeric:
        return None
    values = [c.value for c in numeric if c.value is not None]
    return WidenedRange(lo=min(values), hi=max(values), claims=numeric)
