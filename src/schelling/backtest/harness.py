"""Run the DEU issues through the solver + naive baselines and score against actual outcomes.

Every issue is a point-estimate game, so Monte Carlo is degenerate (zero variance, D3.1): the
harness solves each issue once with the deterministic solver rather than repeating identical draws
(``--draws`` is recorded for interface parity but does not change a point-estimate result, D9.3).
Error is ``|forecast - actual outcome|``; the headline is MAE over the full issue set.

Session 10 adds the "fair fight": real (sourced) capabilities feed the solver AND the weighted-mean
baseline equally (D10.1), and an rp-anchored challenge variant (status quo = the DEU reference
point, D10.4) whose Q is tuned split-sample — tuned on one half, scored on the other (item 4), so a
gain can't be an artifact of tuning.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from schelling.backtest.deu import dataset_sha256
from schelling.mc.monte_carlo import engine_sha
from schelling.schemas.backtest import (
    BacktestRecord,
    DEUIssue,
    IssueError,
    MethodResult,
    OracleSummary,
    SplitSample,
)
from schelling.schemas.question import GameSpec
from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.model import run

# A forecaster maps a whole issue (so it can read the reference point) to a point forecast.
Forecaster = Callable[[DEUIssue], float]

_Q_GRID = (0.3, 0.5, 0.7, 0.9)  # candidate status-quo probabilities for the rp variant (Q < 1)


def weighted_mean_forecast(game: GameSpec) -> float:
    """The compromise model / naive baseline: capability x salience weighted mean of positions.

    With equal capability (D9.2) this is the salience-weighted mean; with sourced capability
    (D10.1) it is the influence-weighted mean — the classic DEU 'compromise' prediction. Falls
    back to the plain mean if all weights are zero.
    """
    num = 0.0
    den = 0.0
    for a in game.actors:
        w = a.capability.mode * a.salience.mode
        num += w * a.position.mode
        den += w
    if den == 0.0:
        positions = [a.position.mode for a in game.actors]
        return sum(positions) / len(positions)
    return num / den


def median_position_forecast(game: GameSpec) -> float:
    """Naive baseline: the (unweighted) median of the actors' positions."""
    positions = sorted(a.position.mode for a in game.actors)
    n = len(positions)
    mid = n // 2
    if n % 2 == 1:
        return positions[mid]
    return (positions[mid - 1] + positions[mid]) / 2.0


def solver_forecast(game: GameSpec, config: SolverConfig) -> float:
    """The challenge solver's headline forecast for one issue: the converged weighted median."""
    return run(game, config).forecast_median


def _challenge(cfg: SolverConfig) -> Forecaster:
    return lambda iss: solver_forecast(iss.game, cfg)


def _rp_challenge(q: float) -> Forecaster:
    """A challenge forecaster anchoring the status quo to each issue's reference point (D10.4)."""

    def forecast(iss: DEUIssue) -> float:
        cfg = SolverConfig(q=q, reference_point=iss.reference_point)
        return solver_forecast(iss.game, cfg)

    return forecast


@dataclass(frozen=True)
class _Method:
    key: str
    label: str
    kind: str
    forecaster: Forecaster
    config: dict[str, str | float | int | bool | None]


def _solver_method(key: str, label: str, kind: str, cfg: SolverConfig) -> _Method:
    return _Method(key, label, kind, _challenge(cfg), cfg.model_dump(mode="json"))


def _base_methods() -> list[_Method]:
    """Two solver configs, two naive baselines, and an R x Q sweep."""
    methods = [
        _solver_method(
            "solver_paper",
            "Solver — paper-faithful (dynamic R, Q=1, risk on)",
            "solver",
            SolverConfig(),
        ),
        _solver_method(
            "solver_risk_off", "Solver — risk off", "solver", SolverConfig(apply_risk=False)
        ),
        _Method(
            "baseline_wmean",
            "Compromise — capability x salience weighted mean",
            "baseline",
            lambda iss: weighted_mean_forecast(iss.game),
            {},
        ),
        _Method(
            "baseline_median",
            "Baseline — median actor position",
            "baseline",
            lambda iss: median_position_forecast(iss.game),
            {},
        ),
    ]
    for rmode in (RangeMode.DYNAMIC, RangeMode.FIXED):
        for q in (1.0, 0.5):
            cfg = SolverConfig(range_mode=rmode, q=q)
            methods.append(
                _solver_method(
                    f"sweep_{rmode.value}_q{q}", f"R={rmode.value}, Q={q:g}", "sweep", cfg
                )
            )
    return methods


def _errors(forecaster: Forecaster, issues: Sequence[DEUIssue]) -> list[float]:
    return [abs(forecaster(iss) - iss.outcome) for iss in issues]


def _mae(forecaster: Forecaster, issues: Sequence[DEUIssue]) -> float:
    errs = _errors(forecaster, issues)
    return sum(errs) / len(errs)


def _method_result(method: _Method, issues: Sequence[DEUIssue]) -> tuple[MethodResult, list[float]]:
    """Compute one method's per-issue errors and summary statistics (errors in issue order)."""
    errors = _errors(method.forecaster, issues)
    n = len(errors)
    mae = sum(errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    ordered = sorted(errors)
    mid = n // 2
    median_error = ordered[mid] if n % 2 == 1 else (ordered[mid - 1] + ordered[mid]) / 2.0
    return (
        MethodResult(
            key=method.key,
            label=method.label,
            kind=method.kind,
            config=method.config,
            mae=mae,
            rmse=rmse,
            median_error=median_error,
            max_error=max(errors),
            errors=errors,
        ),
        errors,
    )


def _tune_rp_split_sample(
    issues: Sequence[DEUIssue], q_grid: Sequence[float]
) -> tuple[float, SplitSample]:
    """Tune the rp-anchored challenge's Q on a training half and score it on a held-out half.

    Deterministic interleaved split (even issue indices = train, odd = test) keeps both halves
    balanced across the three treaty periods. Selection minimizes train MAE; the reported test MAE
    is the honest number (item 4). Ties in train MAE break to the larger Q for determinism.
    """
    train = list(issues[0::2])
    test = list(issues[1::2])
    train_mae = {q: _mae(_rp_challenge(q), train) for q in q_grid}
    selected = min(q_grid, key=lambda q: (train_mae[q], -q))
    test_mae = _mae(_rp_challenge(selected), test)
    test_baseline = _mae(lambda iss: weighted_mean_forecast(iss.game), test)
    split = SplitSample(
        objective="rp-anchored challenge: status-quo probability Q",
        tuned_param="q",
        candidates=list(q_grid),
        selected=selected,
        train_n=len(train),
        test_n=len(test),
        train_mae=train_mae[selected],
        test_mae=test_mae,
        test_baseline_mae=test_baseline,
        passed=test_mae < test_baseline,
    )
    return selected, split


_BASELINES = ["baseline_wmean", "baseline_median"]


def run_backtest(
    issues: Sequence[DEUIssue],
    *,
    csv_path: Path,
    dataset_label: str,
    seed: int = 42,
    draws: int = 2000,
    capability: float = 100.0,
    capability_mode: str = "equal",
    reference_point: bool = False,
    q_grid: Sequence[float] = _Q_GRID,
    worst_n: int = 10,
    created_at: str | None = None,
    oracle: OracleSummary | None = None,
) -> BacktestRecord:
    """Score every method over ``issues`` and assemble the deterministic :class:`BacktestRecord`.

    The gate (fixed in advance): the primary config must beat BOTH naive baselines on MAE. When
    ``reference_point`` is set, the primary is the rp-anchored challenge at the split-sample-tuned
    Q (this is the Session-10 "gate v2" — real capabilities + reference point vs the equally
    equipped weighted mean).
    """
    if not issues:
        raise ValueError("no issues to backtest (the DEU CSV produced an empty issue set).")

    methods = _base_methods()
    split_sample: SplitSample | None = None
    primary_key = "solver_paper"
    primary_forecaster: Forecaster = _challenge(SolverConfig())

    if reference_point:
        selected_q, split_sample = _tune_rp_split_sample(issues, q_grid)
        primary_forecaster = _rp_challenge(selected_q)
        methods.append(
            _Method(
                "challenge_rp",
                f"Challenge — rp-anchored, Q={selected_q:g} (tuned split-sample)",
                "solver",
                primary_forecaster,
                {"reference_point": "per-issue DEU rp", "q": selected_q, "range_mode": "dynamic"},
            )
        )
        primary_key = "challenge_rp"

    results: list[MethodResult] = []
    errors_by_key: dict[str, list[float]] = {}
    for method in methods:
        result, errors = _method_result(method, issues)
        results.append(result)
        errors_by_key[method.key] = errors

    mae = {r.key: r.mae for r in results}
    gate_passed = all(mae[primary_key] < mae[b] for b in _BASELINES)

    primary_errors = errors_by_key[primary_key]
    ranked = sorted(range(len(issues)), key=lambda i: (-primary_errors[i], issues[i].issue_id))
    worst = [
        IssueError(
            issue_id=issues[i].issue_id,
            proposal_name=issues[i].proposal_name,
            forecast=primary_forecaster(issues[i]),
            actual=issues[i].outcome,
            error=primary_errors[i],
        )
        for i in ranked[:worst_n]
    ]

    return BacktestRecord(
        dataset=dataset_label,
        dataset_sha256=dataset_sha256(csv_path),
        n_issues=len(issues),
        seed=seed,
        draws=draws,
        capability=capability,
        capability_mode=capability_mode,
        reference_point_used=reference_point,
        split_sample=split_sample,
        oracle=oracle,
        engine_version=engine_sha(),
        created_at=created_at,
        methods=results,
        primary_method=primary_key,
        baseline_methods=list(_BASELINES),
        gate_passed=gate_passed,
        worst_issues=worst,
    )
