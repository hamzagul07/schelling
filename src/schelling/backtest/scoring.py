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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from schelling.report.bands import BANDED, LINEAR, NONE, _sorted_bands, band_containing, map_bands
from schelling.schemas.forecast import (
    CrowdForecastRecord,
    ForecastRecord,
    LLMForecastRecord,
)
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


# --------------------------------------------------------- the binary track (Session 47, D47.1)
BINARY_BRIER = "binary-brier"


def binary_prob_met(record: ForecastRecord, rubric: ResolutionRubric | None) -> float | None:
    """P(binary criterion met) = the share of the record's MC draws that fall in the rubric's
    ``binary_met_bands`` (D47.1). None unless the rubric is banded AND declares that mapping.

    ``rubric`` is passed explicitly (for records that look their rubric up rather than embed it).
    The band-to-binary mapping is read from ``rubric.binary_met_bands`` — declared, never inferred.
    """
    if rubric is None or not rubric.bands or not rubric.binary_met_bands:
        return None
    readout = map_bands(record)
    if readout.kind != BANDED or not readout.per_band:
        return None
    met = set(rubric.binary_met_bands)
    return sum(bp.probability for bp in readout.per_band if bp.band.label in met)


def binary_realized(actual: float, rubric: ResolutionRubric | None) -> bool | None:
    """Whether the realized ``actual`` lands in a MET band (D47.1); None if no mapping declared."""
    if rubric is None or not rubric.bands or not rubric.binary_met_bands:
        return None
    band = band_containing(actual, rubric)
    return band is not None and band.label in set(rubric.binary_met_bands)


def brier_binary(p_met: float, met: bool) -> float:
    """Binary Brier score ``(p - y)^2`` for the probability of the criterion being met (D47.1).

    Ranges [0, 1]; 0 is a perfect confident call, lower is better. This is the ONLY track the crowd
    baseline is scored on, and it never mixes with the continuum ``|median - actual|`` track.
    """
    return (p_met - (1.0 if met else 0.0)) ** 2


# --------------------------------------------------------------------------- rubric dispatch
def primary(rubric: ResolutionRubric | None) -> str:
    """The rubric's declared primary metric, or the legacy default ``absolute_error`` (D40.1).

    Every question sealed before D40 declares no ``primary_metric``, so this returns
    ``absolute_error`` for them — their committed primary is untouched.
    """
    if rubric is None or not rubric.primary_metric:
        return DEFAULT_PRIMARY
    return rubric.primary_metric


def score_record(
    record: ForecastRecord | LLMForecastRecord | CrowdForecastRecord, actual: float
) -> ScoreCard:
    """Score one sealed record against its realized ``actual`` (Session 49, D49.1 dispatch).

    Dispatches on the record schema so **any** ledger row is scoreable:

    * :class:`ForecastRecord` — Brier + log over a banded rubric, or CRPS from cached draws for an
      arithmetic rubric; ``absolute_error`` always included.
    * :class:`LLMForecastRecord` — no cached draws, so ``absolute_error`` always, plus Brier + log
      from its reported ``band_probabilities`` when the rubric is banded.
    * :class:`CrowdForecastRecord` — a binary-track-only family (D47.2); returns a card with **no**
      continuum score and a note pointing at ``binary_track``, never a ``|median - actual|`` number.

    The score named by :func:`primary` is marked ``role="primary"``; all others are ``secondary``.
    """
    if isinstance(record, CrowdForecastRecord):
        return ScoreCard(
            question_id=record.question_id,
            actual=actual,
            median=record.ensemble.median,
            kind=NONE,
            scores=[],
            realized_band=None,
            note="Crowd baseline — scored on the binary track only (D47.2); no continuum "
            "score. See scoring.binary_track for its Brier on P(criterion met).",
        )
    rubric = record.game.resolution_rubric if record.game else None
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
    if isinstance(record, LLMForecastRecord):
        kind, realized_band, note = _score_llm_bands(record, rubric, actual, scores)
    else:
        kind, realized_band, note = _score_forecast_bands(record, rubric, actual, scores)
    if kind == NONE:
        note = note or "No resolution rubric committed; scored on the raw draws and median only."
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
        kind=kind,
        scores=marked,
        realized_band=realized_band,
        note=note,
    )


def _score_forecast_bands(
    record: ForecastRecord, rubric: ResolutionRubric | None, actual: float, scores: list[Score]
) -> tuple[str, str | None, str]:
    """Append Brier+log (banded) or CRPS (arithmetic) for a ForecastRecord; (kind, band, note)."""
    readout = map_bands(record)
    realized_band: str | None = None
    note = ""
    if readout.kind == BANDED and readout.per_band:
        probs = [bp.probability for bp in readout.per_band]
        band = band_containing(actual, rubric)
        realized_band = band.label if band is not None else None
        idx = next(
            (i for i, bp in enumerate(readout.per_band) if band is not None and bp.band == band), -1
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
    if readout.kind == LINEAR and not record.outcome_distribution:
        note = note or "Arithmetic rubric with no cached draws; only absolute error is available."
    return readout.kind, realized_band, note


def _score_llm_bands(
    record: LLMForecastRecord, rubric: ResolutionRubric | None, actual: float, scores: list[Score]
) -> tuple[str, str | None, str]:
    """Append Brier+log for an llm-judgment record from its reported ``band_probabilities`` (D49.1).

    The llm baseline carries no cached draws, so its band probabilities are the model's own reported
    shares, aligned to the sorted bands by label. An arithmetic (band-less) rubric yields only the
    absolute error already in ``scores``.
    """
    if rubric is None:
        return NONE, None, ""
    if not rubric.bands:
        return (
            LINEAR,
            None,
            (
                "LLM-judgment baseline on an arithmetic rubric — no cached draws; scored on "
                "|median - actual| only."
            ),
        )
    bands = _sorted_bands(rubric)
    probs = [float(record.band_probabilities.get(b.label, 0.0)) for b in bands]
    band = band_containing(actual, rubric)
    realized_band = band.label if band is not None else None
    idx = next((i for i, b in enumerate(bands) if band is not None and b == band), -1)
    floor = 0.5 / record.n_samples if record.n_samples else 1e-9
    scores.append(
        Score(
            BRIER,
            brier_score(probs, idx),
            "lower",
            "sum_i (p_i - y_i)^2 over the rubric's bands, from the llm's reported band shares.",
        )
    )
    scores.append(
        Score(
            LOG,
            log_score(probs, idx, floor=floor),
            "higher",
            f"ln(reported share on the realized band); floored at 0.5/{record.n_samples} samples.",
        )
    )
    note = "LLM-judgment baseline — Brier/log from the model's reported band probabilities."
    return BANDED, realized_band, note


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


# ---------------------------------------------------- the binary track for compare (D47.1)
# The binary track is scored on its own graded count, and NEVER combined with the continuum track.
MIN_GRADED_BINARY = 10


@dataclass(frozen=True)
class BinaryScore:
    """One record's binary-track score: P(met), the realized yes/no, and the Brier."""

    question_id: str
    model: str  # challenge | compromise | llm-judgment (derived P(met)) | crowd-metaculus
    p_met: float
    realized_met: bool
    brier: float


def load_crowd_records(runs_dir: Path) -> list[CrowdForecastRecord]:
    """Load every ``CrowdForecastRecord`` (model=crowd-metaculus) JSON in ``runs_dir``."""
    records: list[CrowdForecastRecord] = []
    if not runs_dir.exists():
        return records
    for path in sorted(runs_dir.glob("*.json")):
        try:
            records.append(CrowdForecastRecord.model_validate_json(path.read_text()))
        except ValueError:
            continue  # not a crowd record
    return records


def binary_track(
    records: list[ForecastRecord],
    crowd_records: list[CrowdForecastRecord],
    grades: dict[str, float],
    rubric_for: Callable[[str], ResolutionRubric | None],
) -> list[BinaryScore]:
    """Brier on the binary track for every graded question that declares a band-to-binary mapping.

    Solver records contribute a *derived* P(met) (their met-band draw share); crowd records
    contribute their own ``binary_prob_met``. Questions without a declared mapping have no binary
    track and are skipped. Deterministically ordered. Never touches the continuum track (D47.1).
    """
    out: list[BinaryScore] = []
    for r in records:
        actual = grades.get(r.question_id)
        if actual is None:
            continue
        rubric = rubric_for(r.question_id)
        met = binary_realized(actual, rubric)
        p = binary_prob_met(r, rubric)
        if met is None or p is None:
            continue
        out.append(BinaryScore(r.question_id, r.model, p, met, brier_binary(p, met)))
    for c in crowd_records:
        actual = grades.get(c.question_id)
        if actual is None:
            continue
        rubric = c.game.resolution_rubric if c.game is not None else None
        met = binary_realized(actual, rubric)
        if met is None:
            continue
        out.append(
            BinaryScore(
                c.question_id, c.model, c.binary_prob_met, met, brier_binary(c.binary_prob_met, met)
            )
        )
    return sorted(out, key=lambda s: (s.question_id, s.model))


def format_binary_track(scores: list[BinaryScore]) -> list[str]:
    """Render the binary track: per-record Brier + a per-family ranking once enough are graded.

    The refuse-to-rank guard applies to THIS track's own count of graded questions (D47.1), separate
    from the continuum track's; the two are never combined.
    """
    if not scores:
        return [
            "Binary track (Brier on P(criterion met)): no question graded on the binary track yet."
        ]
    lines = ["Binary track (Brier on P(criterion met)) — crowd baselines + derived solver P(met):"]
    for s in scores:
        outcome = "MET" if s.realized_met else "not met"
        lines.append(
            f"  {s.question_id} {s.model:<14} p={s.p_met:.3f} vs {outcome}, Brier {s.brier:.4f}"
        )
    graded_questions = len({s.question_id for s in scores})
    if graded_questions < MIN_GRADED_BINARY:
        lines.append(
            f"  Exploratory: {graded_questions}/{MIN_GRADED_BINARY} questions graded on the binary "
            "track — no family ranking claimed before the threshold (its own count, D47.1)."
        )
    else:
        by_model: dict[str, list[float]] = {}
        for s in scores:
            by_model.setdefault(s.model, []).append(s.brier)
        ranked = sorted(by_model.items(), key=lambda kv: (sum(kv[1]) / len(kv[1]), kv[0]))
        for i, (model, briers) in enumerate(ranked, 1):
            lines.append(
                f"  {i}. {model:<15} mean Brier {sum(briers) / len(briers):.4f} (n={len(briers)})"
            )
    return lines


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
