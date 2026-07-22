"""Map a ForecastRecord's Monte-Carlo draws through its question's ResolutionRubric bands (D22.2).

Pure, deterministic, LLM-free. Given a record, ``map_bands`` classifies every cached draw into the
rubric's bands and returns per-band probabilities, the modal band, and the band the median lands in.
Banded rubrics get the full treatment; arithmetic/linear rubrics (no structured bands) and the
no-rubric case degrade gracefully with an explanatory note. Same record + same rubric = identical
readout.
"""

from __future__ import annotations

from dataclasses import dataclass

from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec, ResolutionRubric, RubricBand

BANDED = "banded"
LINEAR = "linear"
NONE = "none"


@dataclass(frozen=True)
class BandProb:
    """One band with its share of the draws and whether it is the modal / median band."""

    band: RubricBand
    probability: float  # share of draws that fell in this band (0..1)
    is_modal: bool
    is_median: bool


@dataclass(frozen=True)
class BandReadout:
    """The band mapping of one record: kind, per-band probabilities, and the headline bands."""

    kind: str  # BANDED | LINEAR | NONE
    per_band: list[BandProb]  # empty unless kind == BANDED
    modal_band: RubricBand | None
    median_band: RubricBand | None
    median: float
    p10: float
    p90: float
    n_draws: int
    note: str  # graceful explanation for LINEAR / NONE (empty for BANDED)


def _sorted_bands(rubric: ResolutionRubric) -> list[RubricBand]:
    return sorted(rubric.bands, key=lambda b: b.lo)


def _band_index(value: float, bands: list[RubricBand]) -> int:
    """Index of the band ``value`` falls in: the last band whose ``lo`` it clears (clamped).

    Using ``lo`` as a threshold partitions float draws with no gaps even where the written
    integer ``[lo, hi]`` ranges leave unit holes (e.g. 0-9 then 10-24).
    """
    idx = 0
    for i, b in enumerate(bands):
        if value >= b.lo:
            idx = i
    return idx


def band_containing(value: float, rubric: ResolutionRubric | None) -> RubricBand | None:
    """The band a single value lands in, or None when the rubric has no structured bands."""
    if rubric is None or not rubric.bands:
        return None
    bands = _sorted_bands(rubric)
    return bands[_band_index(value, bands)]


def map_bands(record: ForecastRecord) -> BandReadout:
    """Classify the record's cached draws through its rubric's bands (see module docstring)."""
    rubric = record.game.resolution_rubric if record.game else None
    e = record.ensemble
    if rubric is None:
        return BandReadout(
            NONE,
            [],
            None,
            None,
            e.median,
            e.p10,
            e.p90,
            e.n_draws,
            "No resolution rubric is committed for this question, so the outcome cannot be mapped "
            "to bands; the raw settlement distribution is shown instead.",
        )
    if not rubric.bands:
        return BandReadout(
            LINEAR,
            [],
            None,
            None,
            e.median,
            e.p10,
            e.p90,
            e.n_draws,
            "This rubric maps the outcome arithmetically onto the 0-100 continuum (no discrete "
            "bands); it is graded by the distance |median - actual|.",
        )
    bands = _sorted_bands(rubric)
    draws = record.outcome_distribution
    n = len(draws)
    counts = [0] * len(bands)
    for v in draws:
        counts[_band_index(v, bands)] += 1
    probs = [c / n for c in counts] if n else [0.0] * len(bands)
    # Modal band: highest share, ties broken by lowest index for determinism. With no cached
    # draws, fall back to the band the median lands in.
    median_i = _band_index(e.median, bands)
    modal_i = max(range(len(bands)), key=lambda i: (probs[i], -i)) if n else median_i
    per = [BandProb(b, probs[i], i == modal_i, i == median_i) for i, b in enumerate(bands)]
    return BandReadout(BANDED, per, bands[modal_i], bands[median_i], e.median, e.p10, e.p90, n, "")


def compromise_point(game: GameSpec) -> float:
    """The compromise model's closed-form settlement: the capability x salience weighted mean of
    mode positions (the second-solver cross-check; matches ``advise._compromise_settlement``).

    Falls back to the plain mean of positions when the total weight is non-positive.
    """
    num = 0.0
    den = 0.0
    for a in game.actors:
        w = a.capability.mode * a.salience.mode
        num += w * a.position.mode
        den += w
    if den <= 0.0:
        positions = [a.position.mode for a in game.actors]
        return sum(positions) / len(positions)
    return num / den
