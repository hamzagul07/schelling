"""Run the DEU issues through the solver + naive baselines and score against actual outcomes.

Every issue is a point-estimate game, so Monte Carlo is degenerate (zero variance, D3.1): the
harness solves each issue once with the deterministic solver rather than repeating identical draws
(``--draws`` is recorded for interface parity but does not change a point-estimate result, D9.3).
Error is ``|forecast - actual outcome|``; the headline is MAE over the full issue set.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from schelling.backtest.deu import dataset_sha256
from schelling.mc.monte_carlo import engine_version
from schelling.schemas.backtest import BacktestRecord, DEUIssue, IssueError, MethodResult
from schelling.schemas.question import GameSpec
from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.model import run

Forecaster = Callable[[GameSpec], float]


def weighted_mean_forecast(game: GameSpec) -> float:
    """Naive baseline: the capability x salience weighted mean of actor positions.

    With capability fixed constant across actors (D9.2) this is the salience-weighted mean — a
    classic DEU 'compromise' baseline. Falls back to the plain mean if all weights are zero.
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
    """The solver's headline forecast for one issue: the converged weighted median."""
    return run(game, config).forecast_median


@dataclass(frozen=True)
class _Method:
    key: str
    label: str
    kind: str
    forecaster: Forecaster
    config: dict[str, str | float | int | bool]


def _solver_method(key: str, label: str, kind: str, cfg: SolverConfig) -> _Method:
    return _Method(key, label, kind, lambda g: solver_forecast(g, cfg), cfg.model_dump(mode="json"))


def _methods() -> list[_Method]:
    """The methods reported: two solver configs, two naive baselines, and an R x Q sweep."""
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
            "Baseline — capability x salience weighted mean",
            "baseline",
            weighted_mean_forecast,
            {},
        ),
        _Method(
            "baseline_median",
            "Baseline — median actor position",
            "baseline",
            median_position_forecast,
            {},
        ),
    ]
    # Config sweep over R-mode and Q (each solved deterministically).
    for rmode in (RangeMode.DYNAMIC, RangeMode.FIXED):
        for q in (1.0, 0.5):
            cfg = SolverConfig(range_mode=rmode, q=q)
            methods.append(
                _solver_method(
                    f"sweep_{rmode.value}_q{q}", f"R={rmode.value}, Q={q:g}", "sweep", cfg
                )
            )
    return methods


def _method_result(method: _Method, issues: Sequence[DEUIssue]) -> tuple[MethodResult, list[float]]:
    """Compute one method's per-issue errors and summary statistics (errors in issue order)."""
    errors: list[float] = []
    for issue in issues:
        forecast = method.forecaster(issue.game)
        errors.append(abs(forecast - issue.outcome))
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


_PRIMARY = "solver_paper"
_BASELINES = ["baseline_wmean", "baseline_median"]


def run_backtest(
    issues: Sequence[DEUIssue],
    *,
    csv_path: Path,
    dataset_label: str,
    seed: int = 42,
    draws: int = 2000,
    capability: float = 100.0,
    worst_n: int = 10,
    created_at: str | None = None,
) -> BacktestRecord:
    """Score every method over ``issues`` and assemble the deterministic :class:`BacktestRecord`.

    The gate (fixed in advance): the primary solver config must beat BOTH naive baselines on MAE.
    """
    if not issues:
        raise ValueError("no issues to backtest (the DEU CSV produced an empty issue set).")

    results: list[MethodResult] = []
    errors_by_key: dict[str, list[float]] = {}
    for method in _methods():
        result, errors = _method_result(method, issues)
        results.append(result)
        errors_by_key[method.key] = errors

    mae = {r.key: r.mae for r in results}
    gate_passed = all(mae[_PRIMARY] < mae[b] for b in _BASELINES)

    # Worst issues by the primary method's absolute error (ties broken by issue id for determinism).
    primary_errors = errors_by_key[_PRIMARY]
    primary_cfg = SolverConfig()  # the paper-faithful config the primary method uses
    ranked = sorted(range(len(issues)), key=lambda i: (-primary_errors[i], issues[i].issue_id))
    worst = [
        IssueError(
            issue_id=issues[i].issue_id,
            proposal_name=issues[i].proposal_name,
            forecast=solver_forecast(issues[i].game, primary_cfg),
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
        engine_version=engine_version(),
        created_at=created_at,
        methods=results,
        primary_method=_PRIMARY,
        baseline_methods=list(_BASELINES),
        gate_passed=gate_passed,
        worst_issues=worst,
    )
