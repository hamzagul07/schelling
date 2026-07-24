"""The research corpus: the frozen evidence set a draft is formalized from (Session 38, D38).

Every real-world claim carries a confidence level — ``established`` (multiple independent primary
sources), ``reported`` (a single credible source), ``contested`` (sources disagree; all readings
recorded), or ``inferred`` (no source; the model's reasoning, stated as such). The corpus is the
deterministic input to ``formalize --corpus``: given the same corpus, the evidence the formalizer
sees is fixed, and the confidence tags drive each coordinate's range width by a committed rule.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["established", "reported", "contested", "inferred"]
# Ordered weakest -> strongest for deriving a coordinate's confidence from its claims.
CONFIDENCE_ORDER: tuple[Confidence, ...] = ("inferred", "reported", "established")


class ResearchSource(BaseModel):
    """One fetched source, cached by URL with the date it was first retrieved (D38.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    title: str
    retrieved_at: str  # ISO date; preserved on re-runs so cached sources are never re-dated
    snippet: str = ""


class Claim(BaseModel):
    """One extracted claim, tagged with a confidence level and the coordinate it addresses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    confidence: Confidence
    source_urls: list[str] = Field(default_factory=list)  # supporting sources (empty => inferred)
    # The game coordinate this claim informs, as ``<actor_id>.<param>`` (position/salience/
    # capability), or "" for general/background evidence that isn't a single coordinate.
    addresses: str = ""
    # For contested claims (and any point-valued claim): the reading(s) on the 0-100 continuum. A
    # coordinate whose claims record disagreeing readings is widened to span them (D38.4).
    readings: list[float] = Field(default_factory=list)

    def key(self) -> str:
        """A stable identity for deduplication (same text + coordinate = same claim)."""
        return f"{self.addresses}␟{self.text.strip().lower()}"


class RoundLog(BaseModel):
    """One research round's accounting — what it added and what it cost (D38.5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    round: int
    kind: str  # "survey" | "targeted" | "contradiction"
    new_claims: int
    new_sources: int
    gaps_remaining: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    cumulative_cost_usd: float = 0.0


class ResearchCorpus(BaseModel):
    """The accumulated evidence: sources, claims, the per-round log, and where it stopped.

    Resumable — reloaded from disk and continued (D38.1). Sources are unique by URL; claims are
    unique by :meth:`Claim.key`; the per-coordinate confidence is *derived* from the claims, so a
    contradiction cannot be silently resolved to one reading.
    """

    model_config = ConfigDict(extra="forbid")

    situation_hash: str  # sha256 of the situation text this corpus was built from
    frozen_at: str
    sources: list[ResearchSource] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    gaps_remaining: list[str] = Field(default_factory=list)
    rounds: list[RoundLog] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    stopped_reason: str = ""  # "marginal" | "no_gaps" | "budget" | ""

    def source_urls(self) -> set[str]:
        return {s.url for s in self.sources}

    def claim_keys(self) -> set[str]:
        return {c.key() for c in self.claims}

    def coordinate_confidence(self) -> dict[str, Confidence]:
        """Derive each coordinate's confidence from the claims that address it (D38.4).

        A coordinate whose claims disagree — more than one distinct reading, or any claim already
        tagged ``contested`` — is ``contested`` (never collapsed). Otherwise it takes the strongest
        confidence among its claims; a coordinate with no claim is ``inferred``.
        """
        by_coord: dict[str, list[Claim]] = {}
        for c in self.claims:
            if c.addresses:
                by_coord.setdefault(c.addresses, []).append(c)
        out: dict[str, Confidence] = {}
        for coord, claims in by_coord.items():
            distinct_readings = {round(r, 6) for c in claims for r in c.readings}
            if any(c.confidence == "contested" for c in claims) or len(distinct_readings) > 1:
                out[coord] = "contested"
            else:
                strongest = max(
                    (c.confidence for c in claims),
                    key=lambda cf: CONFIDENCE_ORDER.index(cf) if cf in CONFIDENCE_ORDER else -1,
                )
                out[coord] = strongest
        return out

    def coordinate_readings(self) -> dict[str, list[float]]:
        """Every recorded reading per coordinate (for widening a contested range to span them)."""
        out: dict[str, list[float]] = {}
        for c in self.claims:
            if c.addresses and c.readings:
                out.setdefault(c.addresses, []).extend(c.readings)
        return {k: sorted(v) for k, v in out.items()}
