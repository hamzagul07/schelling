"""Proper scoring rules for a sealed forecast against its realized outcome (Session 40, D40.1).

Pure, deterministic, LLM-free. A *proper* scoring rule reads the whole forecast distribution, not
just its median, and is minimized (or maximized) in expectation only by reporting one's true
beliefs — so it cannot be gamed by hedging. This module computes, from a :class:`ForecastRecord`'s
cached Monte-Carlo draws and a realized outcome on the 0-100 continuum:

* **Brier score** and the **logarithmic score** over a banded rubric's bands. The probability
  vector is the share of draws in each band (the same mapping the report already shows via
  ``report.bands.map_bands``); the band the outcome lands in is the realized category.
* **CRPS** (Continuous Ranked Probability Score) for an arithmetic / continuous rubric, computed
  from the empirical draw distribution. **CRPS reduces to the absolute error ``|forecast - actual|``
  when the forecast is a point mass** (all draws equal) — so it *generalizes* the ``|median -
  actual|`` metric the ledger already uses rather than replacing it. See :func:`crps_empirical`.

Integrity (D40.1, non-negotiable): the three questions sealed before D40 keep ``|median - actual|``
as their **primary** metric exactly as their committed rubrics state — none declares a
``primary_metric``, so :func:`primary` returns ``absolute_error`` for them. The proper scores are
computed and reported **alongside**, explicitly labelled secondary. Questions sealed from now on use
the updated template, which declares the proper rule primary and absolute error secondary.

Orientation differs by rule and is carried on every :class:`Score` so a reader never has to guess:
Brier, CRPS and absolute error are ``lower``-is-better (0 = perfect); the logarithmic score is
``higher``-is-better (0 = perfect, negative worse). Same record + same outcome = identical scores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from schelling.report.bands import BANDED, LINEAR, NONE, band_containing, map_bands
from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import ResolutionRubric

# Metric names — stable identifiers used in rubric declarations, reports, and tests.
BRIER = "brier"
LOG = "log"
CRPS = "crps"
ABSOLUTE_ERROR = "absolute_error"

# Legacy default: a rubric that declares no primary metric is graded on |median - actual|, exactly
# as every question sealed before D40 states. See ResolutionRubric.primary_metric.
DEFAULT_PRIMARY = ABSOLUTE_ERROR


@dataclass(frozen=True)
class Score:
    """One score with its orientation and a one-line definition, so the number self-describes."""

    name: str
    value: float
    orientation: str  # "lower" (0 best, larger worse) | "higher" (0 best, negative worse)
    definition: str
    role: str = "secondary"  # "primary" | "secondary"


@dataclass(frozen=True)
class ScoreCard:
    """Every applicable score for one record against its realized outcome, primary marked."""

    question_id: str
    actual: float
    median: float
    kind: str  # BANDED | LINEAR | NONE — the rubric's shape (report.bands)
    scores: list[Score] = field(default_factory=list)
    realized_band: str | None = None  # label of the band the outcome fell in (banded only)
    note: str = ""

    @property
    def primary(self) -> Score | None:
        return next((s for s in self.scores if s.role == "primary"), None)

    @property
    def secondary(self) -> list[Score]:
        return [s for s in self.scores if s.role == "secondary"]


# --------------------------------------------------------------------------- the raw rules
def absolute_error(median: float, actual: float) -> float:
    """``|median - actual|`` on the 0-100 continuum — the ledger's existing primary metric."""
    return abs(median - actual)


def brier_score(probs: list[float], realized_index: int) -> float:
    """Multi-category Brier score ``sum_i (p_i - y_i)^2``, realized category ``y = 1`` (D40.1).

    Ranges [0, 2]; 0 is a perfect confident call, lower is better. ``probs`` need not sum to
    exactly 1 (they are empirical draw shares); the definition is unchanged either way.
    """
    return sum((p - (1.0 if i == realized_index else 0.0)) ** 2 for i, p in enumerate(probs))


def log_score(probs: list[float], realized_index: int, *, floor: float) -> float:
    """Logarithmic score ``ln(p_realized)`` — higher is better, 0 is perfect (D40.1).

    A realized band that received **zero** draws would give ``-inf``; that is a genuine "you gave
    the outcome zero probability" failure, but we floor the probability at ``floor`` (caller passes
    half a draw, ``0.5 / n_draws``) so the penalty is large-but-finite and tied to the ensemble's
    own resolution rather than to machine infinity. The flooring is disclosed, never silent.
    """
    p = probs[realized_index] if 0 <= realized_index < len(probs) else 0.0
    return math.log(max(p, floor))


def crps_empirical(draws: list[float], actual: float) -> float:
    """CRPS of the empirical (ensemble) forecast distribution against ``actual`` (D40.1).

    ``CRPS = E|X - y| - 1/2 E|X - X'|`` for X, X' iid from the forecast. Evaluated exactly on the
    sample: with the draws sorted ascending ``x_(1..n)`` (1-indexed),

        E|X - y|   = mean_i |x_i - y|
        E|X - X'|  = (2 / n^2) * sum_i (2i - n - 1) * x_(i)

    which is O(n log n), not the naive O(n^2) double sum. Lower is better; the score is in the
    units of the 0-100 continuum. **Point mass** (all draws equal) -> the spread term is 0 and CRPS
    collapses to ``|forecast - actual|``, so this generalizes the ledger's absolute-error metric.
    """
    n = len(draws)
    if n == 0:
        return float("nan")
    xs = sorted(draws)
    mean_abs = sum(abs(x - actual) for x in xs) / n
    # sum_i (2i - n - 1) x_(i), i from 1..n; E|X - X'| = 2/n^2 * that. spread term = 1/2 E|X-X'|.
    weighted = sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs))
    spread = weighted / (n * n)  # = 1/2 * E|X - X'|
    return mean_abs - spread


# --------------------------------------------------------------------------- rubric dispatch
def primary(rubric: ResolutionRubric | None) -> str:
    """The rubric's declared primary metric, or the legacy default ``absolute_error`` (D40.1).

    Every question sealed before D40 declares no ``primary_metric``, so this returns
    ``absolute_error`` for them — their committed primary is untouched.
    """
    if rubric is None or not rubric.primary_metric:
        return DEFAULT_PRIMARY
    return rubric.primary_metric


def score_record(record: ForecastRecord, actual: float) -> ScoreCard:
    """Score one record against its realized ``actual``, marking the rubric's primary metric.

    Dispatches on the rubric shape: a banded rubric gets Brier + log over its bands; an arithmetic
    or rubric-less record gets CRPS from the draws. ``absolute_error`` is always included. The score
    named by :func:`primary` is marked ``role="primary"``; all others are ``secondary``.
    """
    rubric = record.game.resolution_rubric if record.game else None
    readout = map_bands(record)
    median = record.ensemble.median
    scores: list[Score] = [
        Score(
            ABSOLUTE_ERROR,
            absolute_error(median, actual),
            "lower",
            "|median - actual| on the 0-100 continuum.",
        )
    ]
    realized_band: str | None = None
    note = ""
    if readout.kind == BANDED and readout.per_band:
        probs = [bp.probability for bp in readout.per_band]
        band = band_containing(actual, rubric)
        realized_band = band.label if band is not None else None
        idx = next(
            (i for i, bp in enumerate(readout.per_band) if band is not None and bp.band == band),
            -1,
        )
        floor = 0.5 / readout.n_draws if readout.n_draws else 1e-9
        scores.append(
            Score(
                BRIER,
                brier_score(probs, idx),
                "lower",
                "sum_i (p_i - y_i)^2 over the rubric's bands; 0 perfect, 2 worst.",
            )
        )
        scores.append(
            Score(
                LOG,
                log_score(probs, idx, floor=floor),
                "higher",
                f"ln(draw-share on the realized band); floored at 0.5/{readout.n_draws} draws.",
            )
        )
    elif record.outcome_distribution:
        scores.append(
            Score(
                CRPS,
                crps_empirical(record.outcome_distribution, actual),
                "lower",
                "CRPS of the empirical draws; reduces to |forecast - actual| at a point mass.",
            )
        )
    else:
        note = "No cached draws — only the median-based absolute error is available."
    if readout.kind == NONE:
        note = note or "No resolution rubric committed; scored on the raw draws and median only."
    elif readout.kind == LINEAR and not record.outcome_distribution:
        note = note or "Arithmetic rubric with no cached draws; only absolute error is available."
    declared = primary(rubric)
    marked = [
        Score(s.name, s.value, s.orientation, s.definition, role="primary")
        if s.name == declared
        else s
        for s in scores
    ]
    # If the declared primary isn't computable (e.g. declares brier but has no bands), fall back to
    # absolute error as primary so a card always has exactly one primary.
    if not any(s.role == "primary" for s in marked):
        marked = [
            Score(s.name, s.value, s.orientation, s.definition, role="primary")
            if s.name == ABSOLUTE_ERROR
            else s
            for s in marked
        ]
        note = (note + " ").lstrip() + (
            f"Declared primary '{declared}' is not computable for this record; "
            "reported absolute error as primary."
        )
    return ScoreCard(
        question_id=record.question_id,
        actual=actual,
        median=median,
        kind=readout.kind,
        scores=marked,
        realized_band=realized_band,
        note=note,
    )


def load_forecast_records(runs_dir: Path) -> list[ForecastRecord]:
    """Load every ``ForecastRecord`` JSON in ``runs_dir`` (skipping non-solver records, e.g. the
    llm-judgment records, which use a different schema and carry no cached draws to score)."""
    records: list[ForecastRecord] = []
    if not runs_dir.exists():
        return records
    for path in sorted(runs_dir.glob("*.json")):
        try:
            records.append(ForecastRecord.model_validate_json(path.read_text()))
        except ValueError:
            continue  # an llm-judgment or other non-ForecastRecord file — not scored here
    return records


def score_runs(records: list[ForecastRecord], grades: dict[str, float]) -> list[ScoreCard]:
    """Score every record whose question is graded, sorted by (question_id, model) for determinism.

    Used by ``schelling compare`` to report proper scores **alongside** the median-based MAE
    ranking. Only records with cached draws yield proper scores; the rest still get absolute error.
    """
    scored = [(r, grades[r.question_id]) for r in records if r.question_id in grades]
    scored.sort(key=lambda ra: (ra[0].question_id, ra[0].model, ra[0].run_id))
    return [score_record(r, actual) for r, actual in scored]


def format_scorecard(card: ScoreCard) -> str:
    """Render a scorecard as plain text: primary first, secondaries labelled, orientations shown."""
    lines = [
        f"{card.question_id}: actual {card.actual:g}, median {card.median:g} ({card.kind} rubric)"
    ]
    if card.realized_band:
        lines.append(f"  realized band: {card.realized_band}")
    prim = card.primary
    if prim is not None:
        arrow = "lower better" if prim.orientation == "lower" else "higher better"
        lines.append(f"  PRIMARY   {prim.name:<15} {prim.value:+.4f}  ({arrow})")
    for s in card.secondary:
        arrow = "lower better" if s.orientation == "lower" else "higher better"
        lines.append(f"  secondary {s.name:<15} {s.value:+.4f}  ({arrow})")
    if card.note:
        lines.append(f"  note: {card.note}")
    return "\n".join(lines)
