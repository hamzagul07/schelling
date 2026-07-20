"""Octant classification of a dyad and the offer (position move) it implies.

BUILD_PLAN §4 step 6; Scholz §6.1, figure 6, eqs. 35-36. See ``scholz_extract.md`` and
DECISIONS.md D2.x (ambiguities A3, A4 — the primary replication risk).

Each ordered dyad ``(i, j)`` is classified from i's viewpoint using
``(a, b) = (E^i(U_ij), E^j(U_ji))``. The result names a relation and, when a move is implied,
which actor moves and to what position.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Relation(StrEnum):
    """Dyadic relation type (Scholz figure 6)."""

    CONFLICT = "conflict"  # confrontation, lower-EU actor concedes fully
    COMPROMISE = "compromise"  # upper-hand actor; other moves part way (eqs. 35-36)
    COMPEL = "compel"  # upper-hand dominant; other moves fully
    STATUS_QUO = "status_quo"  # both EUs negative; no one moves
    STALEMATE = "stalemate"  # tie within conflict; no one moves


@dataclass(frozen=True)
class Offer:
    """A proposed move for one actor arising from a single dyad.

    ``mover`` is the actor index that would move; ``new_position`` is where to. ``None`` mover
    means the relation implies no move (status quo / stalemate). ``enforceability`` is the
    proposing (winning) actor's expected utility — how well it can make the offer stick
    (Scholz §6.2); used to pick which offer a mover accepts.
    """

    relation: Relation
    mover: int | None
    new_position: float | None
    enforceability: float = 0.0


def classify(
    a: float, b: float, i: int, j: int, x_i: float, x_j: float, conflict_resolves: bool = True
) -> Offer:
    """Classify dyad ``(i, j)`` and return the implied offer (Scholz §6.1, figure 6).

    ``a = E^i(U_ij)``, ``b = E^j(U_ji)``. Conventions (see scholz_extract.md):

    * Conflict (``a > 0, b > 0``): the lower-EU actor concedes fully to the higher-EU actor;
      an exact tie is a stalemate (no move).
    * Compromise (opposite signs, upper hand's ``|EU|`` larger): the other actor moves part way,
      by eqs. 35/36 — ``x_mover += (x_other - x_mover) * |EU_mover / EU_other|``.
    * Compel (opposite signs, upper hand's ``|EU|`` smaller): the other actor moves fully.
    * Status quo (``a < 0, b < 0``): no one moves.
    """
    if a > 0.0 and b > 0.0:
        # Conflict: both expect to gain -> "uncertain outcome" (BDM 1997). Optionally no move.
        if not conflict_resolves:
            return Offer(Relation.CONFLICT, mover=None, new_position=None)
        # Otherwise the lower-EU actor concedes fully to the higher-EU actor.
        if a > b:
            return Offer(Relation.CONFLICT, mover=j, new_position=x_i, enforceability=a)
        if b > a:
            return Offer(Relation.CONFLICT, mover=i, new_position=x_j, enforceability=b)
        return Offer(Relation.STALEMATE, mover=None, new_position=None)

    if a < 0.0 and b < 0.0:
        # Both expect to lose from challenging: status quo.
        return Offer(Relation.STATUS_QUO, mover=None, new_position=None)

    # Opposite signs: one of a, b is > 0 and the other < 0 (zeros fall through to status quo).
    if a > 0.0 and b < 0.0:
        # i has the upper hand; j is the mover toward i.
        if abs(a) >= abs(b):  # compromise+: j moves part way to i (eq. 35)
            x_hat = (x_i - x_j) * abs(b / a)
            return Offer(Relation.COMPROMISE, mover=j, new_position=x_j + x_hat, enforceability=a)
        # compel+: j moves fully to i
        return Offer(Relation.COMPEL, mover=j, new_position=x_i, enforceability=a)

    if a < 0.0 and b > 0.0:
        # j has the upper hand; i is the mover toward j.
        if abs(b) >= abs(a):  # compromise-: i moves part way to j (eq. 36)
            x_hat = (x_i - x_j) * abs(a / b)
            return Offer(Relation.COMPROMISE, mover=i, new_position=x_i - x_hat, enforceability=b)
        # compel-: i moves fully to j
        return Offer(Relation.COMPEL, mover=i, new_position=x_j, enforceability=b)

    # Any remaining case (a or b exactly 0): treat as status quo (no clear upper hand).
    return Offer(Relation.STATUS_QUO, mover=None, new_position=None)
