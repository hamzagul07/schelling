"""Coercive / out-of-domain case library + head-to-head harness (Session 11 / follow-up).

The library is a directory of hand-transcribed case files (``data/coercive-cases/*.json``), each a
``{"library_version", "transcription", "cases": [...], "notes": [...]}`` document; the per-case
schema is documented in ``data/coercive-cases/README.md``. Each case carries an expert-coded
stakeholder table (position/salience/capability on 0-100), a natural-language continuum, one or more
dated outcome readings (the ``primary`` one is scored; others are secondary), a source citation, an
``ex_ante`` flag, and a verification status. Values are on a 0-100 continuum.

The harness scores challenge (real inputs) vs the compromise mean vs the gravity/regime successors
by MAE with paired bootstrap CIs. It is deliberately conservative: **no verdict is claimed** while
the library is tiny, unverified, or out of the coercive domain — those caveats surface in the note.
The coercive interstate classics (Hong Kong 1985, Iran 1984, Feder) remain the quest (D11.1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from schelling.backtest.successor import compromise_estimate, load_candidate, predict_for_game
from schelling.schemas.question import Continuum, GameSpec
from schelling.schemas.stakeholders import Actor, TriangularEstimate
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

DEFAULT_LIBRARY = Path("data/coercive-cases")
_METHODS = ("challenge", "compromise", "gravity", "regime")


@dataclass(frozen=True)
class CoerciveCase:
    """One case: an expert-coded game plus its primary historical outcome (+ metadata)."""

    case_id: str
    title: str
    domain: str  # e.g. "coercive_interstate" | "domestic_elite_bargaining"
    source: str
    ex_ante: bool
    verified: bool
    continuum: str
    outcome: float  # the primary (paper-horizon) reading, scored by the harness
    outcome_secondary: list[float]  # other dated readings, reported not scored
    published_forecast: str  # the incumbent model's stated forecast (prose), for context
    reference_point: float | None
    game: GameSpec


def _point(value: object) -> TriangularEstimate:
    return TriangularEstimate.point(float(value))  # type: ignore[arg-type]


def _build_game(case: dict) -> GameSpec:  # type: ignore[type-arg]
    cont = case["continuum"]
    actors = [
        Actor(
            id=str(a["id"]),
            name=str(a["name"]),
            position=_point(a["position"]),
            salience=_point(a["salience"]),
            capability=_point(a["capability"]),
        )
        for a in case["actors"]
    ]
    return GameSpec(
        question_id=str(case["case_id"]),
        frozen_at=str(case.get("data_collected", "unknown")),
        continuum=Continuum(
            label=str(cont["label"]),
            anchor_0=str(cont["anchor_0"]),
            anchor_100=str(cont["anchor_100"]),
        ),
        actors=actors,
        template="multilateral_bargaining",
        horizon="one_shot",
        notes=str(case.get("title", "")),
    )


def _split_outcomes(case: dict) -> tuple[float, list[float]]:  # type: ignore[type-arg]
    """Primary (scored) outcome and secondary readings, per the ``primary`` flag / first-listed."""
    outcomes = case["outcomes"]
    primary: float | None = None
    secondary: list[float] = []
    for out in outcomes.values():
        value = float(out["proposed_value"])
        if out.get("primary") and primary is None:
            primary = value
        else:
            secondary.append(value)
    if primary is None:  # convention: the first-listed outcome is primary
        items = list(outcomes.values())
        primary = float(items[0]["proposed_value"])
        secondary = [float(o["proposed_value"]) for o in items[1:]]
    return primary, secondary


def load_library(path: Path = DEFAULT_LIBRARY) -> list[CoerciveCase]:
    """Load every case from a library file or directory (``*.json``); [] if nothing is there."""
    if path.is_dir():
        files = sorted(path.glob("*.json"))
    elif path.exists():
        files = [path]
    else:
        files = []

    cases: list[CoerciveCase] = []
    for file in files:
        data = json.loads(file.read_text())
        file_verified = bool(data.get("transcription", {}).get("verified", True))
        for c in data.get("cases", []):
            primary, secondary = _split_outcomes(c)
            cases.append(
                CoerciveCase(
                    case_id=c["case_id"],
                    title=c.get("title", ""),
                    domain=c.get("domain", ""),
                    source=c["source"],
                    ex_ante=bool(c.get("ex_ante", False)),
                    verified=file_verified,
                    continuum=c["continuum"]["label"],
                    outcome=primary,
                    outcome_secondary=secondary,
                    published_forecast=c.get("published_model_forecast", {}).get("value_note", ""),
                    reference_point=(
                        None if c.get("reference_point") is None else float(c["reference_point"])
                    ),
                    game=_build_game(c),
                )
            )
    return cases


@dataclass(frozen=True)
class CoerciveMethodResult:
    key: str
    mae: float
    delta_vs_compromise: float  # mae - compromise_mae (negative = beats the mean)
    ci_lo: float
    ci_hi: float


@dataclass(frozen=True)
class CoerciveReport:
    n_cases: int
    methods: list[CoerciveMethodResult]
    note: str


def _forecast(method: str, case: CoerciveCase) -> float:
    if method == "compromise":
        return compromise_estimate(case.game)
    if method == "challenge":
        return run(case.game, SolverConfig(reference_point=case.reference_point)).forecast_median
    return predict_for_game(load_candidate(method), case.game, case.reference_point)


def _caveat(cases: list[CoerciveCase]) -> str:
    reasons: list[str] = []
    n = len(cases)
    if n < 15:
        reasons.append(f"N={n} is tiny")
    if any(not c.verified for c in cases):
        reasons.append("transcriptions UNVERIFIED")
    domains = {c.domain for c in cases}
    if domains and not all(d.startswith("coercive") for d in domains):
        reasons.append("out of the coercive domain (domestic/cooperative cases)")
    if reasons:
        return "Illustrative only — no verdict claimed (" + "; ".join(reasons) + ")."
    return f"N={n} cases."


def head_to_head(
    cases: list[CoerciveCase], *, seed: int = 20260721, n_boot: int = 2000
) -> CoerciveReport:
    """Score every model on the library with paired bootstrap CIs vs the compromise mean."""
    if not cases:
        return CoerciveReport(
            n_cases=0,
            methods=[],
            note="No cases yet — coercive library deferred (sources paywalled; see D11.1).",
        )
    y = np.array([c.outcome for c in cases])
    abs_err = {m: np.abs(np.array([_forecast(m, c) for c in cases]) - y) for m in _METHODS}
    comp = abs_err["compromise"]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(cases), size=(n_boot, len(cases)))

    results = []
    for m in _METHODS:
        deltas = abs_err[m][idx].mean(axis=1) - comp[idx].mean(axis=1)
        lo, hi = np.percentile(deltas, [2.5, 97.5])
        results.append(
            CoerciveMethodResult(
                key=m,
                mae=float(abs_err[m].mean()),
                delta_vs_compromise=float(abs_err[m].mean() - comp.mean()),
                ci_lo=float(lo),
                ci_hi=float(hi),
            )
        )
    return CoerciveReport(n_cases=len(cases), methods=results, note=_caveat(cases))
