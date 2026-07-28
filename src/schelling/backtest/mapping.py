"""Apply a rubric's machine-readable outcome mapping to a real-world figure (Session 49, D49.2).

Pure, deterministic, LLM-free. Turns a real-world outcome value into a 0-100 continuum settlement
point using the rubric's structured mapping — the executable form of the ``outcome_mapping`` prose:

* An **arithmetic** rubric carries a :class:`~schelling.schemas.question.LinearMap`
  (``continuum = intercept + slope * raw``, clamped, rounded by the declared rule).
* A **banded** rubric has no linear map; a banded question's ``--actual`` is already a placement on
  the continuum (the grader reads the event and places it per the committed band descriptions), so
  the identity is returned and band membership is read separately via ``report.bands``.

The rounding rule is declared on the map, never left to a library default (Python ``round`` is
banker's rounding, which resolves a ``.5`` tie differently). ``nearest_int_half_up`` rounds ties
to the larger integer; on the clamped ``[0, 100]`` continuum that equals round-half-away-from-zero.
"""

from __future__ import annotations

import math

from schelling.schemas.question import LinearMap, ResolutionRubric

NEAREST_INT_HALF_UP = "nearest_int_half_up"


def round_half_up(value: float) -> float:
    """Round to the nearest integer, ties to the larger integer (D49.2).

    ``math.floor(value + 0.5)`` sends ``x.5`` up to ``x+1`` (50.5 -> 51), unlike ``round`` which
    would give 50 (banker's rounding). The continuum is clamped ``>= 0`` so there is no ambiguity
    about which way a negative tie should go.
    """
    return float(math.floor(value + 0.5))


def apply_linear_map(mapping: LinearMap, raw: float) -> float:
    """``clamp(intercept + slope * raw)`` then the declared rounding — the continuum settlement."""
    if mapping.rounding != NEAREST_INT_HALF_UP:
        raise ValueError(f"unsupported rounding rule {mapping.rounding!r}")
    continuum = mapping.intercept + mapping.slope * raw
    clamped = max(mapping.clamp_lo, min(mapping.clamp_hi, continuum))
    return round_half_up(clamped)


def map_outcome(rubric: ResolutionRubric | None, raw: float) -> tuple[float, str]:
    """Map a real-world outcome ``raw`` onto the 0-100 continuum via the rubric (D49.2).

    Returns ``(continuum_value, note)``. An arithmetic rubric with a ``outcome_map`` applies it; a
    banded rubric (or a rubric with no structured map) treats ``raw`` as an already-placed continuum
    value and returns it unchanged, with a note saying so.
    """
    if rubric is not None and rubric.outcome_map is not None:
        value = apply_linear_map(rubric.outcome_map, raw)
        m = rubric.outcome_map
        return value, (
            f"mapped {raw:g} {m.unit} -> {value:g} on the 0-100 continuum via the rubric's "
            f"linear map (continuum = {m.intercept:g} + {m.slope:g} * raw, clamped "
            f"[{m.clamp_lo:g}, {m.clamp_hi:g}], {m.rounding})"
        )
    if rubric is not None and rubric.bands:
        return raw, (
            f"banded rubric — treated --actual {raw:g} as an already-placed 0-100 continuum value; "
            "band membership is read from the committed bands"
        )
    return raw, f"no structured mapping — treated --actual {raw:g} as a 0-100 continuum value"
