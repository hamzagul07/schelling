"""Ingest the DEU dataset CSV into normalized :class:`DEUIssue` records.

The DEU III dataset (Arregui & Perarnaud 2021, doi:10.34810/data53, CC BY 4.0) is a
semicolon-delimited CSV: one row per controversial issue, with each actor's position and salience
on a 0-100 policy scale, a reference point ``rp``, and the actual decision outcome ``out``. It
records NO capability, so we assign a fixed constant to every actor (D9.2). Rows whose outcome is
missing (blank or the sentinel 999) or that have fewer than ``min_actors`` participating actors are
dropped. See ``data/deu/Readme_DEU_III.txt`` for the collection methodology.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from schelling.backtest.capability import capabilities_for_issue, regime_for_year
from schelling.schemas.backtest import DEUIssue
from schelling.schemas.question import Continuum, GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate

# Actor column codes in the DEU CSV, in header order: two EU institutions + 28 member states.
ACTOR_CODES: tuple[str, ...] = (
    "com",
    "ep",
    "at",
    "be",
    "bu",
    "cr",
    "cy",
    "cz",
    "dk",
    "ee",
    "fi",
    "fr",
    "de",
    "el",
    "hu",
    "ie",
    "it",
    "lv",
    "lt",
    "lu",
    "mt",
    "nl",
    "pl",
    "pt",
    "ro",
    "si",
    "sk",
    "es",
    "se",
    "uk",
)

ACTOR_NAMES: dict[str, str] = {
    "com": "European Commission",
    "ep": "European Parliament",
    "at": "Austria",
    "be": "Belgium",
    "bu": "Bulgaria",
    "cr": "Croatia",
    "cy": "Cyprus",
    "cz": "Czech Republic",
    "dk": "Denmark",
    "ee": "Estonia",
    "fi": "Finland",
    "fr": "France",
    "de": "Germany",
    "el": "Greece",
    "hu": "Hungary",
    "ie": "Ireland",
    "it": "Italy",
    "lv": "Latvia",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "mt": "Malta",
    "nl": "Netherlands",
    "pl": "Poland",
    "pt": "Portugal",
    "ro": "Romania",
    "si": "Slovenia",
    "sk": "Slovakia",
    "es": "Spain",
    "se": "Sweden",
    "uk": "United Kingdom",
}

# Values outside [0, 100] are DEU missing-data sentinels (e.g. 999), not real positions/outcomes.
_SCALE_MIN, _SCALE_MAX = 0.0, 100.0

DEFAULT_CSV = Path("data/deu/Dataset_DEU_III.csv")


def dataset_sha256(csv_path: Path) -> str:
    """SHA-256 of the source CSV bytes — pins the exact dataset version into the record."""
    return hashlib.sha256(csv_path.read_bytes()).hexdigest()


def _num(cell: str) -> float | None:
    """Parse a DEU numeric cell; blank or an out-of-scale sentinel (e.g. 999) -> ``None``."""
    cell = cell.strip()
    if cell == "":
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    if value < _SCALE_MIN or value > _SCALE_MAX:
        return None
    return value


def _year(datestr: str) -> int | None:
    """Parse a DEU DD-MM-YY date to a 4-digit year (YY >= 90 -> 19YY, else 20YY)."""
    parts = datestr.strip().split("-")
    if len(parts) != 3 or not parts[-1].isdigit():
        return None
    yy = int(parts[-1])
    return 1900 + yy if yy >= 90 else 2000 + yy


def load_deu_issues(
    csv_path: Path = DEFAULT_CSV,
    *,
    capability: float = 100.0,
    sourced_capability: bool = False,
    min_actors: int = 3,
) -> list[DEUIssue]:
    """Parse the DEU CSV into normalized issues (solver-ready games + actual outcomes).

    Each actor with both a position and a salience present becomes a point-estimate
    :class:`Actor`. Capability is either a fixed constant (``capability``, the Session-9 default,
    D9.2) or, when ``sourced_capability=True``, the treaty-regime Council power for that issue's
    decision year (Session-10, D10.1). Issues without a valid outcome, or with fewer than
    ``min_actors`` participating actors, are dropped.
    """
    with csv_path.open(newline="") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    header = rows[0]
    col = {name: i for i, name in enumerate(header)}

    issues: list[DEUIssue] = []
    for row in rows[1:]:
        outcome = _num(row[col["out"]])
        if outcome is None:  # missing / sentinel outcome -> not scoreable
            continue

        frozen = row[col["finact"]].strip() or row[col["intro"]].strip() or "unknown"
        present = [
            (code, pos, sal)
            for code in ACTOR_CODES
            if (pos := _num(row[col["p" + code]])) is not None
            and (sal := _num(row[col["s" + code]])) is not None
        ]
        if len(present) < min_actors:
            continue

        if sourced_capability:
            year = _year(frozen) or 2007  # a Nice-era fallback; every real row parses
            caps = capabilities_for_issue([c for c, _, _ in present], year)
            cap_note = f"sourced capability ({regime_for_year(year)} regime, D10.1)"
        else:
            caps = {c: capability for c, _, _ in present}
            cap_note = f"capability fixed at {capability:g} (DEU records none)"

        actors = [
            Actor(
                id=code,
                name=ACTOR_NAMES[code],
                position=TriangularEstimate.point(pos),
                salience=TriangularEstimate.point(sal),
                capability=TriangularEstimate.point(caps[code]),
            )
            for code, pos, sal in present
        ]

        issue_id = row[col["isnr"]]
        game = GameSpec(
            question_id=issue_id,
            frozen_at=frozen,
            continuum=Continuum(
                label="DEU policy scale (0-100)",
                anchor_0="one extreme policy alternative on this issue",
                anchor_100="the opposite extreme policy alternative on this issue",
            ),
            actors=actors,
            template="multilateral_bargaining",
            horizon="one_shot",
            notes=f"DEU issue {issue_id}; {cap_note}.",
        )
        issues.append(
            DEUIssue(
                issue_id=issue_id,
                proposal_id=row[col["prnr"]],
                proposal_name=row[col["prname"]],
                procedure=row[col["proc"]].strip(),
                outcome=outcome,
                reference_point=_num(row[col["rp"]]),
                game=game,
            )
        )
    return issues
