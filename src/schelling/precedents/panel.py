"""Build the reference-class panel and the outside-view divergence diagnostic (D29.3, D29.5).

The panel is the empirical distribution of RATIFIED precedents across the current rubric's bands —
the outside view, never blended into the solver line. The divergence diagnostic fires when the
model's median and the precedent base rate fall in different bands.
"""

from __future__ import annotations

import statistics

from schelling.precedents.schemas import PrecedentSet
from schelling.report.bands import band_containing
from schelling.schemas.forecast import ForecastRecord, Precedent, PrecedentPanel
from schelling.schemas.question import GameSpec

DIVERGENCE_LABEL = "OUTSIDE VIEW DISAGREES WITH STRUCTURAL MODEL"


def is_ratified(pset: PrecedentSet) -> bool:
    """A set counts as ratified only once a human quoted a ratification and accepted placements."""
    return bool(pset.ratification_note.strip()) and any(p.ratified for p in pset.precedents)


def _band_distribution(precedents: list[Precedent], game: GameSpec) -> dict[str, float]:
    """Fraction of ex-ante ratified precedents whose placement lands in each rubric band."""
    rubric = game.resolution_rubric
    if rubric is None or not rubric.bands or not precedents:
        return {}
    counts: dict[str, int] = {b.label: 0 for b in rubric.bands}
    for p in precedents:
        band = band_containing(p.proposed_placement, rubric)
        if band is not None:
            counts[band.label] += 1
    n = sum(counts.values()) or 1
    return {label: c / n for label, c in counts.items() if c}


def build_precedent_panel(pset: PrecedentSet, game: GameSpec) -> PrecedentPanel:
    """Assemble the panel from the RATIFIED precedents (D29.2-D29.3).

    The reference class is sessions-at-risk (D30.1): a base rate is computed **only when the
    enumeration is complete** — the ratified ex-ante precedents span the full ``sessions_at_risk``
    population. Otherwise the class is INCOMPLETE and no distribution is produced (the fraction
    covered is reported instead), so a biased sample never masquerades as a base rate.
    """
    ratified = [p for p in pset.precedents if p.ratified]
    ex_ante = [p for p in ratified if p.ex_ante_codable]
    hindsight = [p for p in ratified if not p.ex_ante_codable]
    n_covered = len(ex_ante)
    complete = pset.sessions_at_risk is not None and n_covered >= pset.sessions_at_risk
    placements = [p.proposed_placement for p in ex_ante]
    return PrecedentPanel(
        source_model=pset.source_model,
        ratification_note=pset.ratification_note,
        precedents=ex_ante,
        hindsight_precedents=hindsight,
        band_distribution=_band_distribution(ex_ante, game) if complete else {},
        median_placement=float(statistics.median(placements)) if placements else None,
        blend_weight=0.0,  # never blended
        reference_class=pset.reference_class,
        sessions_at_risk=pset.sessions_at_risk,
        n_covered=n_covered,
        complete=complete,
    )


def coverage_fraction(panel: PrecedentPanel) -> float | None:
    """The fraction of the reference class covered (``n_covered / sessions_at_risk``), or None."""
    if panel.sessions_at_risk:
        return panel.n_covered / panel.sessions_at_risk
    return None


def base_rate_band(panel: PrecedentPanel) -> str | None:
    """The modal band of the precedent distribution, or None when the class is incomplete/empty.

    Only a COMPLETE reference class yields a base rate (D30.1)."""
    if not panel.complete or not panel.band_distribution:
        return None
    return max(panel.band_distribution.items(), key=lambda kv: (kv[1], kv[0]))[0]


def divergence(record: ForecastRecord) -> tuple[str, str] | None:
    """``(model_band, precedent_band)`` when the model's median and the precedent base rate fall in
    different rubric bands, else None (D29.5)."""
    panel = record.precedent_panel
    game = record.game
    if panel is None or game is None or game.resolution_rubric is None:
        return None
    model_band = band_containing(record.ensemble.median, game.resolution_rubric)
    prec_band = base_rate_band(panel)
    if model_band is None or prec_band is None or model_band.label == prec_band:
        return None
    return model_band.label, prec_band


def divergence_line(record: ForecastRecord) -> str:
    """A one-line diagnostic string (empty when there is no divergence)."""
    d = divergence(record)
    if d is None:
        return ""
    model_band, prec_band = d
    return (
        f"{DIVERGENCE_LABEL}: the structural model's median lands in “{model_band}”, "
        f"but the ratified precedent base rate concentrates in “{prec_band}”."
    )
