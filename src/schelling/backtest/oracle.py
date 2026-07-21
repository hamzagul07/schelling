"""DIAGNOSTIC noise-floor oracle for DEU (Session 11, D11.0).

A deliberately flexible model — kernel ridge regression (RBF) over a RICH feature set that includes
position summaries — fit under seeded K-fold cross-validation. Its cross-validated MAE approximates
the *extractable-signal ceiling*: roughly the best any model of these inputs could do. Comparing it
to the compromise weighted mean answers "is the mean near the ceiling, or is there headroom a better
model could exploit?" Pure numpy, deterministic (CLAUDE.md rule 2). This is a DIAGNOSTIC, not a
shipped forecaster — it peeks at the whole dataset via CV and is not a fair out-of-sample model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from schelling.backtest.successor import (
    _gini,
    _herfindahl,
    _polarization,
    _positions,
    _weights,
    compromise_estimate,
)
from schelling.schemas.backtest import DEUIssue, OracleSummary

FloatArray = npt.NDArray[np.float64]


def _weighted_quantiles(pos: FloatArray, w: FloatArray, qs: tuple[float, ...]) -> list[float]:
    """Weighted quantiles of positions (capability x salience weights)."""
    order = np.argsort(pos)
    p, ww = pos[order], w[order]
    if ww.sum() == 0:
        return [float(np.quantile(pos, q)) for q in qs]
    cum = np.cumsum(ww) - 0.5 * ww
    cum /= ww.sum()
    return [float(np.interp(q, cum, p)) for q in qs]


def oracle_features(issue: DEUIssue) -> FloatArray:
    """A rich structural feature vector for one issue, INCLUDING position summaries (D11.0)."""
    game = issue.game
    p, w = _positions(game), _weights(game)
    ws = w / w.sum() if w.sum() > 0 else np.ones_like(w) / len(w)
    wmean = float(ws @ p)
    rp = issue.reference_point if issue.reference_point is not None else wmean
    q10, q25, q50, q75, q90 = _weighted_quantiles(p, w, (0.1, 0.25, 0.5, 0.75, 0.9))
    return np.array(
        [
            wmean,
            float(np.median(p)),
            float(p.mean()),
            float(p.min()),
            float(p.max()),
            float(p.std()),
            q10,
            q25,
            q50,
            q75,
            q90,
            _gini(w),
            _herfindahl(w),
            _polarization(game),
            float(len(game.actors)),
            1.0 if issue.procedure == "COD" else 0.0,
            rp,
            rp - wmean,
        ],
        dtype=np.float64,
    )


def _rbf_kernel(a: FloatArray, b: FloatArray, gamma: float) -> FloatArray:
    d2 = ((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=2)
    return np.exp(-gamma * d2)


def _standardize_pair(x_tr: FloatArray, x_te: FloatArray) -> tuple[FloatArray, FloatArray]:
    mean = x_tr.mean(axis=0)
    std = np.where(x_tr.std(axis=0) < 1e-9, 1.0, x_tr.std(axis=0))
    return (x_tr - mean) / std, (x_te - mean) / std


def _krr_fold_mae(
    x_tr: FloatArray, y_tr: FloatArray, x_te: FloatArray, y_te: FloatArray, gamma: float, lam: float
) -> float:
    a, b = _standardize_pair(x_tr, x_te)
    k = _rbf_kernel(a, a, gamma)
    alpha = np.linalg.solve(k + lam * np.eye(len(a)), y_tr)
    pred = _rbf_kernel(b, a, gamma) @ alpha
    return float(np.abs(pred - y_te).mean())


def _ridge_fold_mae(
    x_tr: FloatArray, y_tr: FloatArray, x_te: FloatArray, y_te: FloatArray, lam: float
) -> float:
    """Linear ridge with an intercept — subsumes the weighted mean (a feature), so the oracle is a
    valid upper bound on quality (it can always fall back to 'just use wmean')."""
    a, b = _standardize_pair(x_tr, x_te)
    a1 = np.column_stack([np.ones(len(a)), a])
    b1 = np.column_stack([np.ones(len(b)), b])
    reg = lam * np.eye(a1.shape[1])
    reg[0, 0] = 0.0  # don't penalize the intercept
    beta = np.linalg.solve(a1.T @ a1 + reg, a1.T @ y_tr)
    return float(np.abs(b1 @ beta - y_te).mean())


@dataclass(frozen=True)
class OracleResult:
    n_issues: int
    folds: int
    best_model: str  # "linear-ridge" | "kernel-ridge:g=..,l=.."
    oracle_mae: float  # cross-validated flexible-model MAE (~ extractable-signal ceiling)
    compromise_mae: float  # compromise weighted mean over the same issues
    gap: float  # compromise_mae - oracle_mae (headroom above the mean; small => mean near ceiling)


def run_oracle(
    issues: list[DEUIssue],
    *,
    folds: int = 5,
    seed: int = 20260721,
    gammas: tuple[float, ...] = (0.01, 0.03, 0.1, 0.3),
    lambdas: tuple[float, ...] = (0.3, 1.0, 3.0, 10.0),
) -> OracleResult:
    """Cross-validated kernel-ridge oracle vs the compromise mean over ``issues`` (D11.0).

    Fold assignment is a seeded permutation (deterministic). Hyperparameters (gamma, lambda) are
    picked by the same CV — this inflates the oracle slightly in its favor, which is fine: the
    oracle is meant to be optimistic (an upper bound on extractable signal), so a small gap to the
    mean is a strong statement.
    """
    x = np.array([oracle_features(i) for i in issues])
    y = np.array([i.outcome for i in issues])
    comp = np.array([compromise_estimate(i.game) for i in issues])
    n = len(issues)

    rng = np.random.default_rng(seed)
    fold_of = rng.permutation(n) % folds

    def cv(scorer: object) -> float:
        total = 0.0
        for f in range(folds):
            te = fold_of == f
            tr = ~te
            total += scorer(x[tr], y[tr], x[te], y[te]) * te.sum()  # type: ignore[operator]
        return total / n

    best: tuple[float, str] | None = None
    for lam in lambdas:
        m = cv(lambda a, b, c, d, lam=lam: _ridge_fold_mae(a, b, c, d, lam))
        if best is None or m < best[0]:
            best = (m, f"linear-ridge:l={lam:g}")
    for gamma in gammas:
        for lam in lambdas:
            m = cv(lambda a, b, c, d, g=gamma, lam=lam: _krr_fold_mae(a, b, c, d, g, lam))
            if best is None or m < best[0]:
                best = (m, f"kernel-ridge:g={gamma:g},l={lam:g}")
    assert best is not None

    compromise_mae = float(np.abs(comp - y).mean())
    return OracleResult(
        n_issues=n,
        folds=folds,
        best_model=best[1],
        oracle_mae=best[0],
        compromise_mae=compromise_mae,
        gap=compromise_mae - best[0],
    )


def oracle_summary(issues: list[DEUIssue], **kw: object) -> OracleSummary:
    """Run the oracle and return the serializable :class:`OracleSummary` for the backtest record."""
    r = run_oracle(issues, **kw)  # type: ignore[arg-type]
    return OracleSummary(
        n_issues=r.n_issues,
        folds=r.folds,
        best_model=r.best_model,
        oracle_mae=r.oracle_mae,
        compromise_mae=r.compromise_mae,
        gap=r.gap,
    )
