"""Reviewer data package for the DEU benchmark (Session 60, D60). POST-HOC, exploratory.

Reproduces the per-issue paired-difference table and the summary statistics sent to the reviewer,
computed from the committed DEU dataset and the harness — deterministic (seeded bootstrap), no
sealed value touched. The **challenge** model is the paper's primary rp-anchored config at the
split-sample-tuned Q; the **compromise** model is the capability x salience weighted mean. Nothing
here is pre-registered; it answers a reviewer's post-hoc questions.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import numpy as np

from schelling.backtest.deu import DEFAULT_CSV, load_deu_issues
from schelling.backtest.harness import _rp_challenge, _tune_rp_split_sample, weighted_mean_forecast
from schelling.schemas.backtest import DEUIssue
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

_Q_GRID = (0.3, 0.5, 0.7, 0.9)
_CSV_HEADER = (
    "issue_id,dossier,procedure,n_actors,outcome,reference_point,"
    "challenge_forecast,compromise_forecast,challenge_ae,compromise_ae,"
    "paired_diff_challenge_minus_compromise,winner"
)


def load_scored_issues(csv_path: Path = DEFAULT_CSV) -> tuple[list[DEUIssue], float]:
    """The 351 sourced-capability issues and the split-sample-tuned Q (the primary config)."""
    issues = load_deu_issues(csv_path, sourced_capability=True)
    q, _ = _tune_rp_split_sample(issues, _Q_GRID)
    return issues, q


def _forecasts(issue: DEUIssue, q: float) -> tuple[float, float]:
    challenge = _rp_challenge(q)(issue)
    compromise = weighted_mean_forecast(issue.game)
    return challenge, compromise


def paired_rows(issues: list[DEUIssue], q: float) -> list[dict[str, object]]:
    """One row per scored issue: forecasts, absolute errors, paired difference, and the winner."""
    rows: list[dict[str, object]] = []
    for iss in issues:
        ch, co = _forecasts(iss, q)
        ch_ae, co_ae = abs(ch - iss.outcome), abs(co - iss.outcome)
        diff = ch_ae - co_ae
        winner = "challenge" if diff < 0 else "compromise" if diff > 0 else "tie"
        rows.append(
            {
                "issue_id": iss.issue_id,
                "dossier": iss.proposal_name,
                "procedure": iss.procedure,
                "n_actors": len(iss.game.actors),
                "outcome": round(iss.outcome, 3),
                "reference_point": ""
                if iss.reference_point is None
                else round(iss.reference_point, 3),
                "challenge_forecast": round(ch, 3),
                "compromise_forecast": round(co, 3),
                "challenge_ae": round(ch_ae, 3),
                "compromise_ae": round(co_ae, 3),
                "paired_diff_challenge_minus_compromise": round(diff, 3),
                "winner": winner,
            }
        )
    return rows


def to_csv(rows: list[dict[str, object]]) -> str:
    """Serialize the paired rows deterministically (dossier names have no commas in DEU III)."""
    lines = [_CSV_HEADER]
    for r in rows:
        lines.append(
            f"{r['issue_id']},{r['dossier']},{r['procedure']},{r['n_actors']},{r['outcome']},"
            f"{r['reference_point']},{r['challenge_forecast']},{r['compromise_forecast']},"
            f"{r['challenge_ae']},{r['compromise_ae']},"
            f"{r['paired_diff_challenge_minus_compromise']},{r['winner']}"
        )
    return "\n".join(lines) + "\n"


def _wemp_crps(issue: DEUIssue, q: float, *, converged: bool) -> float:
    """CRPS of the capability x salience-weighted empirical position distribution vs the outcome.

    On DEU point games the model's *point* forecast has CRPS = absolute error; this is the
    distributional alternative, treating the weighted actor positions as the predictive density.
    """
    g = issue.game
    w = np.array([a.capability.mode * a.salience.mode for a in g.actors], dtype=np.float64)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(g.actors)) / len(g.actors)
    if converged:
        res = run(g, SolverConfig(q=q, reference_point=issue.reference_point))
        pos = np.array(list(res.rounds[-1].positions.values()), dtype=np.float64)
    else:
        pos = np.array([a.position.mode for a in g.actors], dtype=np.float64)
    e_ax = float((w * np.abs(pos - issue.outcome)).sum())
    e_xx = float(0.5 * (w[:, None] * w[None, :] * np.abs(pos[:, None] - pos[None, :])).sum())
    return e_ax - e_xx


def _binom_two_sided(k: int, n: int) -> float:
    """Two-sided sign-test p-value: P(|Binomial(n,0.5) - n/2| >= |k - n/2|)."""
    from math import comb

    if n == 0:
        return 1.0
    dev = abs(k - n / 2)
    total = 0.0
    for x in range(n + 1):
        if abs(x - n / 2) >= dev - 1e-9:
            total += comb(n, x)
    return min(1.0, total / (2.0**n))


def summary(
    issues: list[DEUIssue], q: float, *, seed: int = 59, boot: int = 10000
) -> dict[str, object]:
    """All summary statistics for the package — deterministic given the seed."""
    ch_ae = np.array([abs(_rp_challenge(q)(i) - i.outcome) for i in issues])
    co_ae = np.array([abs(weighted_mean_forecast(i.game) - i.outcome) for i in issues])
    n = len(issues)
    d = ch_ae - co_ae  # per-issue: negative => challenge closer
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(boot, n))

    def ci(stat_fn: object) -> tuple[float, float, float]:
        base = float(stat_fn(ch_ae) - stat_fn(co_ae))  # type: ignore[operator]
        b = np.array([stat_fn(ch_ae[row]) - stat_fn(co_ae[row]) for row in idx])  # type: ignore[operator]
        return base, float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))

    mean_diff, mean_lo, mean_hi = ci(lambda a: a.mean())
    med_diff, med_lo, med_hi = ci(lambda a: np.median(a))
    ch_wins = int((d < -1e-9).sum())
    co_wins = int((d > 1e-9).sum())
    ties = int((np.abs(d) <= 1e-9).sum())
    hits = {t: (float((ch_ae <= t).mean()), float((co_ae <= t).mean())) for t in (5, 10, 20)}
    bins = list(range(0, 101, 10))
    ch_hist = [int(((ch_ae >= lo) & (ch_ae < hi)).sum()) for lo, hi in pairwise(bins)]
    co_hist = [int(((co_ae >= lo) & (co_ae < hi)).sum()) for lo, hi in pairwise(bins)]
    ch_hist[-1] += int((ch_ae >= 100).sum())  # fold the closed top bin
    co_hist[-1] += int((co_ae >= 100).sum())
    crps_ch = float(np.mean([_wemp_crps(i, q, converged=True) for i in issues]))
    crps_co = float(np.mean([_wemp_crps(i, q, converged=False) for i in issues]))
    mde = float((1.959964 + 0.841621) * d.std(ddof=1) / np.sqrt(n))
    return {
        "n": n,
        "q": q,
        "challenge_mean_ae": float(ch_ae.mean()),
        "compromise_mean_ae": float(co_ae.mean()),
        "challenge_median_ae": float(np.median(ch_ae)),
        "compromise_median_ae": float(np.median(co_ae)),
        "mean_ae_diff_ci": (mean_diff, mean_lo, mean_hi),  # the §3 headline CI (26.83 vs 22.99)
        "median_ae_diff_ci": (med_diff, med_lo, med_hi),
        "wins": {"challenge": ch_wins, "compromise": co_wins, "ties": ties},
        "sign_test_p": _binom_two_sided(max(ch_wins, co_wins), ch_wins + co_wins),
        "hit_rates": hits,  # {t: (challenge, compromise)}
        "crps_weighted_empirical": {"challenge": crps_ch, "compromise": crps_co},
        "ae_decile_bins": {"edges": bins, "challenge": ch_hist, "compromise": co_hist},
        "mde_paired_mae": mde,
    }


def write_package_csv(out_dir: Path, csv_path: Path = DEFAULT_CSV) -> Path:
    """Write ``deu-paired-differences.csv`` under ``out_dir``; return the path."""
    issues, q = load_scored_issues(csv_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "deu-paired-differences.csv"
    out.write_text(to_csv(paired_rows(issues, q)))
    return out
