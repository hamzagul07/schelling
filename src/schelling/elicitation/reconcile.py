"""Reconcile independent formalizer drafts into one consensus game (Session 45, D45.2).

Given several drafts of the *same* situation, ``reconcile`` aligns actors by identity, measures how
much the drafts agreed, and emits a consensus :class:`GameSpec` whose ranges are **widened to span
the drafts' disagreement** — not merely each draft's own stated range. The two guarantees that make
this honest:

* **Widening never narrows.** A consensus coordinate's range is ``[min(draft lows), max(draft
  highs)]``, so it contains every draft's own range; its mode is the median of the drafts' modes.
  When the drafts agree the range is unchanged; when they disagree it grows to cover the spread.
* **Minority actors are kept, never dropped.** An actor named by only a minority of drafts
  (``k * 2 < N``) is carried into the consensus game with a ``low_presence`` flag and an evidence
  note, and is disclosed in the agreement table and the game's notes — never silently removed.

Pure and deterministic: same drafts (in the same order) → same consensus game and agreement report.
"""

from __future__ import annotations

from statistics import median

from schelling.schemas.elicitation import (
    ActorAgreement,
    CoordinateAgreement,
    ElicitationSummary,
)
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import Actor, Evidence, TriangularEstimate

_FIELDS = ("position", "salience", "capability")


def _actor_order(games: list[GameSpec]) -> list[str]:
    """Actor ids in first-seen order across the drafts (deterministic, union of all drafts)."""
    order: list[str] = []
    seen: set[str] = set()
    for g in games:
        for a in g.actors:
            if a.id not in seen:
                seen.add(a.id)
                order.append(a.id)
    return order


def _coordinate(present: list[Actor], field: str) -> CoordinateAgreement:
    ests = [getattr(a, field) for a in present]
    modes = [e.mode for e in ests]
    lo = min(e.low for e in ests)  # <= every draft's low  -> range never narrows
    hi = max(e.high for e in ests)  # >= every draft's high
    return CoordinateAgreement(
        field=field,
        draft_modes=modes,
        mode_spread=max(modes) - min(modes),
        consensus_low=lo,
        consensus_mode=float(median(modes)),
        consensus_high=hi,
    )


def reconcile(
    games: list[GameSpec], draft_hashes: list[str] | None = None
) -> tuple[GameSpec, ElicitationSummary]:
    """Align actors across ``games`` and emit ``(consensus_game, summary)`` (D45.2).

    ``games`` are the ``.game`` of each draft, in draft order; ``draft_hashes`` (optional) is the
    ensemble's commitment (the SHA-256 of each draft file). Raises on an empty ensemble.
    """
    if not games:
        raise ValueError("reconcile needs at least one draft")
    n = len(games)
    by_id: dict[str, list[Actor]] = {}
    for g in games:
        for a in g.actors:
            by_id.setdefault(a.id, []).append(a)

    consensus_actors: list[Actor] = []
    agreements: list[ActorAgreement] = []
    minority: list[str] = []
    base = games[0]
    for aid in _actor_order(games):
        present = by_id[aid]
        k = len(present)
        low_presence = k * 2 < n
        coords = [_coordinate(present, f) for f in _FIELDS]
        note = f"consensus of {k}/{n} drafts; ranges widened to span the drafts' disagreement"
        if low_presence:
            note += " — LOW PRESENCE: named by a minority of drafts"
            minority.append(present[0].name)
        consensus_actors.append(
            Actor(
                id=aid,
                name=present[0].name,
                position=TriangularEstimate(
                    low=coords[0].consensus_low,
                    mode=coords[0].consensus_mode,
                    high=coords[0].consensus_high,
                ),
                salience=TriangularEstimate(
                    low=coords[1].consensus_low,
                    mode=coords[1].consensus_mode,
                    high=coords[1].consensus_high,
                ),
                capability=TriangularEstimate(
                    low=coords[2].consensus_low,
                    mode=coords[2].consensus_mode,
                    high=coords[2].consensus_high,
                ),
                evidence=[Evidence(source="elicitation-ensemble", date=base.frozen_at, note=note)],
            )
        )
        agreements.append(
            ActorAgreement(
                actor_id=aid,
                name=present[0].name,
                present_in=k,
                n_drafts=n,
                low_presence=low_presence,
                coordinates=coords,
            )
        )

    notes = (
        f"Consensus of {n} independent formalizer drafts (D45); every coordinate range is widened "
        "to span the drafts' disagreement."
    )
    if minority:
        notes += (
            " Low-presence actors (a minority of drafts named them), retained and flagged: "
            + (", ".join(minority) + ".")
        )
    consensus = base.model_copy(update={"actors": consensus_actors, "notes": notes})
    summary = ElicitationSummary(
        n_drafts=n,
        draft_hashes=list(draft_hashes or []),
        actors=agreements,
    )
    return consensus, summary
