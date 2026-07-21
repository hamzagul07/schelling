"""Coercive head-to-head harness (Session 11, items 1-2 / D11.1).

The coercive case library — expert-coded stakeholder tables from BDM/Policon-lineage crises with
known outcomes (Hong Kong 1985, Iran 1984, Feder's examples, KTAB/Senturion) — could NOT be
assembled this session: the complete tables are in paywalled books/journals, and the in-repo Feder
report omits numeric salience (see D11.1 and the session wrap-up). Per the STOP instruction the
library is deferred; Hassan will supply the printed inputs.

This module is the harness, ready to run the pre-registered head-to-head the moment real cases
arrive: challenge (paper-faithful, real inputs) vs compromise mean vs the gravity/regime successors,
scored by MAE with paired bootstrap CIs, with small-N honesty (no verdict claimed beyond what N
supports). It is validated on a tiny SYNTHETIC fixture only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from schelling.backtest.successor import compromise_estimate, load_candidate, predict_for_game
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

_METHODS = ("challenge", "compromise", "gravity", "regime")


@dataclass(frozen=True)
class CoerciveCase:
    """One coercive case: an expert-coded game plus its known historical outcome."""

    case_id: str
    source: str  # full citation
    ex_ante: bool  # was the coding done before the outcome was known?
    continuum: str
    outcome: float  # the historical outcome on the case's 0-100 continuum
    reference_point: float | None
    game: GameSpec


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


def load_library(path: Path) -> list[CoerciveCase]:
    """Load a coercive library JSON (``{"cases": [...]}``); [] if the file is absent."""
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    cases = []
    for c in data.get("cases", []):
        cases.append(
            CoerciveCase(
                case_id=c["case_id"],
                source=c["source"],
                ex_ante=bool(c["ex_ante"]),
                continuum=c.get("continuum", ""),
                outcome=float(c["outcome"]),
                reference_point=(
                    None if c.get("reference_point") is None else float(c["reference_point"])
                ),
                game=GameSpec.model_validate(c["game"]),
            )
        )
    return cases


def _forecast(method: str, case: CoerciveCase) -> float:
    if method == "compromise":
        return compromise_estimate(case.game)
    if method == "challenge":
        return run(case.game, SolverConfig(reference_point=case.reference_point)).forecast_median
    return predict_for_game(load_candidate(method), case.game, case.reference_point)


def head_to_head(
    cases: list[CoerciveCase], *, seed: int = 20260721, n_boot: int = 2000
) -> CoerciveReport:
    """Score every model on the library with paired bootstrap CIs vs the compromise mean."""
    if not cases:
        return CoerciveReport(
            n_cases=0,
            methods=[],
            note="No coercive cases yet — library deferred (sources paywalled; see D11.1).",
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
    n = len(cases)
    note = (
        f"N={n} is very small — illustrative only; no verdict claimed beyond "
        "what the bootstrap CI supports."
        if n < 15
        else f"N={n} cases."
    )
    return CoerciveReport(n_cases=n, methods=results, note=note)
