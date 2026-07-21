"""ICB (International Crisis Behavior) analog layer (Session 11, item 3 / D11.2).

A feature-tagged, base-rate retrieval over historical interstate crises: given structural tags
(gravity of threat, level of violence, number of actors), return the N most structurally similar
ICB crisis-actor cases and the distribution of their historical outcomes. This is a BASE RATE panel,
kept strictly separate from the deterministic solver forecast (blend weight is disclosed and 0 by
default — the analog outcome distribution is never mixed into the settlement estimate).

Source: Brecher, M., Wilkenfeld, J., et al., International Crisis Behavior Data (ICB), Version 16
(actor-level dataset icb2v16; 1918-2021), sites.duke.edu/icbdata. Codes below follow the ICB
codebook. The raw CSV stays out of the tree (data/icb/, gitignored); a compact table of the fields
used here is committed as package data (`icb_analogs.json`) so the layer ships self-contained.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

# --- ICB codebook mappings (Version 16) ----------------------------------------------------------
OUTCOME = {1: "victory", 2: "compromise", 3: "stalemate", 4: "defeat"}
GRAVITY = {
    1: "economic",
    2: "limited military",
    3: "political",
    4: "territorial",
    5: "influence",
    6: "grave damage",
    7: "existential",
}
VIOLENCE = {1: "none", 2: "minor clashes", 3: "serious clashes", 4: "full-scale war"}
POWER = {1: "small", 2: "middle", 3: "great", 4: "super"}

DEFAULT_CSV = Path("data/icb/icb2v16.csv")
_RESOURCE = "icb_analogs.json"


@dataclass(frozen=True)
class ICBAnalog:
    """One ICB crisis-actor, reduced to the structural tags + outcome the analog layer uses."""

    crisno: int
    crisname: str
    actor: str
    year: int
    outcome: str  # victory | compromise | stalemate | defeat | other
    gravity: int  # 1-7 (0 if unknown)
    violence: int  # 1-4 (0 if unknown)
    n_actors: int
    power: str  # small | middle | great | super | unknown
    protracted: bool


def _int(cell: str) -> int:
    cell = cell.strip()
    return int(cell) if cell.lstrip("-").isdigit() else 0


def build_compact(csv_path: Path = DEFAULT_CSV) -> list[dict[str, object]]:
    """Parse the raw ICB actor-level CSV into the compact committed records (dev-time)."""
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    col = {name: i for i, name in enumerate(rows[0])}

    out: list[dict[str, object]] = []
    for r in rows[1:]:
        oc = _int(r[col["outcom"]])
        out.append(
            {
                "crisno": _int(r[col["crisno"]]),
                "crisname": r[col["crisname"]].strip(),
                "actor": r[col["actor"]].strip(),
                "year": _int(r[col["yrtrig"]]),
                "outcome": OUTCOME.get(oc, "other"),
                "gravity": _int(r[col["gravty"]]),
                "violence": _int(r[col["viol"]]),
                "n_actors": _int(r[col["noactr"]]),
                "power": POWER.get(_int(r[col["powsta"]]), "unknown"),
                "protracted": _int(r[col["pc"]]) >= 2,
            }
        )
    return out


def load_analogs() -> list[ICBAnalog]:
    """Load the committed compact ICB table (no raw CSV needed at runtime)."""
    data = json.loads((files("schelling.analog") / _RESOURCE).read_text())
    return [ICBAnalog(**rec) for rec in data["records"]]


@dataclass(frozen=True)
class AnalogResult:
    """N structural analogs and their pooled historical outcome distribution (a base rate)."""

    n: int
    query: dict[str, float]
    outcome_distribution: dict[str, float]  # label -> fraction, ordered by frequency
    examples: list[ICBAnalog]  # a few nearest analogs, for the reader


_OUTCOME_ORDER = ("victory", "compromise", "stalemate", "defeat", "other")

_ICB_SOURCE = "ICB v16 (icb2v16; Brecher, Wilkenfeld et al.; sites.duke.edu/icbdata)"


def to_panel(result: AnalogResult) -> object:
    """Convert an :class:`AnalogResult` to a report-ready ``AnalogPanel`` (blend weight 0)."""
    from schelling.schemas.forecast import AnalogExample, AnalogPanel

    return AnalogPanel(
        source=_ICB_SOURCE,
        n=result.n,
        query=result.query,
        outcome_distribution=result.outcome_distribution,
        examples=[
            AnalogExample(crisname=a.crisname, year=a.year, actor=a.actor, outcome=a.outcome)
            for a in result.examples
        ],
        blend_weight=0.0,
    )


class ICBAnalogIndex:
    """Feature-tagged nearest-analog retrieval over ICB crises (KnowledgeIndex-style)."""

    def __init__(self, analogs: list[ICBAnalog]) -> None:
        self._analogs = [a for a in analogs if a.gravity and a.violence and a.n_actors]

    @classmethod
    def load(cls) -> ICBAnalogIndex:
        return cls(load_analogs())

    def __len__(self) -> int:
        return len(self._analogs)

    def _distance(self, a: ICBAnalog, gravity: float, violence: float, n_actors: float) -> float:
        # Normalized structural distance: gravity /7, violence /4, log-actor-count /log(35).
        dg = (a.gravity - gravity) / 7.0
        dv = (a.violence - violence) / 4.0
        dn = (math.log(a.n_actors) - math.log(max(n_actors, 1))) / math.log(35.0)
        return dg * dg + dv * dv + dn * dn

    def search(
        self, *, gravity: float, violence: float, n_actors: float, k: int = 30
    ) -> AnalogResult:
        """The k nearest ICB analogs by structural tags, with their outcome distribution.

        Ties broken by crisis number for determinism. The distribution is a historical BASE RATE,
        not a forecast — it is never blended into the solver settlement line (weight 0 by default).
        """
        ranked = sorted(
            self._analogs,
            key=lambda a: (self._distance(a, gravity, violence, n_actors), a.crisno, a.actor),
        )
        nearest = ranked[:k]
        counts: dict[str, int] = {}
        for a in nearest:
            counts[a.outcome] = counts.get(a.outcome, 0) + 1
        n = len(nearest)
        dist = {
            label: counts[label] / n
            for label in sorted(counts, key=lambda x: (-counts[x], _OUTCOME_ORDER.index(x)))
        }
        return AnalogResult(
            n=n,
            query={"gravity": gravity, "violence": violence, "n_actors": n_actors},
            outcome_distribution=dist,
            examples=nearest[:6],
        )
