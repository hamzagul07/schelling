"""Successor-model search over DEU (Session R1): two candidate settlement models.

Both candidates are small, differentiable blends of three component estimates — the compromise
weighted mean, the real-input challenge solver, and the status-quo reference point — fit by
deterministic full-batch Adam in numpy (no sklearn/scipy dependency, byte-identical under fixed
inputs, CLAUDE.md rule 2). They are fit on the committed **train** split, tuned (L2) on **dev**, and
scored on the pre-registered **TEST** split exactly once.

Candidate A — status-quo gravity: ``outcome = λ·wmean + (1-λ)·rp`` on rp issues, λ from a logistic
of a small feature set (decision rule, capability concentration, rp distance from wmean).

Candidate B — regime-aware settlement: softmax regime weights (compromise/challenge/status-quo) over
structural features, prediction = the π-weighted blend of the three component estimates.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from pathlib import Path

import numpy as np
import numpy.typing as npt

from schelling.backtest.deu import DEFAULT_CSV, dataset_sha256, load_deu_issues
from schelling.backtest.split import SPLIT_SEED, load_committed_split, split_counts
from schelling.schemas.backtest import DEUIssue
from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.model import run
from schelling.solver.nash import ks_forecast, nash_forecast
from schelling.solver.pce import pce_forecast
from schelling.solver.qre import run_qre

FloatArray = npt.NDArray[np.float64]
BOOT_SEED = 20260721


# --------------------------------------------------------------- component estimates + features
def _weights(game: GameSpec) -> FloatArray:
    return np.array([a.capability.mode * a.salience.mode for a in game.actors], dtype=np.float64)


def _positions(game: GameSpec) -> FloatArray:
    return np.array([a.position.mode for a in game.actors], dtype=np.float64)


def compromise_estimate(game: GameSpec) -> float:
    w, p = _weights(game), _positions(game)
    return float(p.mean()) if w.sum() == 0 else float(w @ p / w.sum())


def challenge_estimate(game: GameSpec) -> float:
    """The real-input challenge solver forecast (Session 10 sourced-capability game)."""
    return run(game, SolverConfig()).forecast_median


def _gini(x: FloatArray) -> float:
    """Gini coefficient of non-negative weights (0 = equal, →1 = concentrated)."""
    if x.sum() == 0:
        return 0.0
    s = np.sort(x)
    n = s.size
    cum = np.cumsum(s)
    return float((n + 1 - 2 * (cum.sum() / cum[-1])) / n)


def _herfindahl(x: FloatArray) -> float:
    if x.sum() == 0:
        return 0.0
    shares = x / x.sum()
    return float((shares**2).sum())


def _polarization(game: GameSpec) -> float:
    """Salience/capability-weighted std of positions, normalized to [0, 1]."""
    w, p = _weights(game), _positions(game)
    if w.sum() == 0:
        return float(p.std() / 100.0)
    m = w @ p / w.sum()
    return float(np.sqrt(w @ (p - m) ** 2 / w.sum()) / 100.0)


@dataclass(frozen=True)
class IssueData:
    """Everything a candidate needs for one issue (precomputed once)."""

    issue_id: str
    split: str
    outcome: float
    wmean: float
    challenge: float
    rp: float | None
    rule_cod: float  # 1.0 if ordinary procedure (COD), else 0.0
    gini: float
    herfindahl: float
    polarization: float
    n_actors: int

    @property
    def status_quo(self) -> float:
        """The status-quo component: the reference point, or the weighted mean when rp is absent."""
        return self.wmean if self.rp is None else self.rp

    @property
    def rp_offset(self) -> float:
        return 0.0 if self.rp is None else (self.rp - self.wmean) / 100.0

    @property
    def rp_dist(self) -> float:
        return 0.0 if self.rp is None else abs(self.rp - self.wmean) / 100.0


def build_issue_data(issue: DEUIssue, split: str) -> IssueData:
    game = issue.game
    return IssueData(
        issue_id=issue.issue_id,
        split=split,
        outcome=issue.outcome,
        wmean=compromise_estimate(game),
        challenge=challenge_estimate(game),
        rp=issue.reference_point,
        rule_cod=1.0 if issue.procedure == "COD" else 0.0,
        gini=_gini(_weights(game)),
        herfindahl=_herfindahl(_weights(game)),
        polarization=_polarization(game),
        n_actors=len(game.actors),
    )


# --------------------------------------------------------------- deterministic Adam (pure numpy)
def _adam(grad_fn: object, x0: FloatArray, *, iters: int = 4000, lr: float = 0.05) -> FloatArray:
    x = x0.astype(np.float64).copy()
    m = np.zeros_like(x)
    v = np.zeros_like(x)
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, iters + 1):
        g = grad_fn(x)  # type: ignore[operator]
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        mh = m / (1 - b1**t)
        vh = v / (1 - b2**t)
        x = x - lr * mh / (np.sqrt(vh) + eps)
    return x


def _standardize(matrix: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Column mean/std (std floored at 1e-9); returned so the SAME transform applies to dev/TEST."""
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std = np.where(std < 1e-9, 1.0, std)
    return mean, std


def _sigmoid(z: FloatArray) -> FloatArray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


# --------------------------------------------------------------- Candidate A — status-quo gravity
_A_FEATURES = ("rule_cod", "herfindahl", "rp_dist")


def _a_matrix(rows: list[IssueData]) -> FloatArray:
    return np.array([[r.rule_cod, r.herfindahl, r.rp_dist] for r in rows], dtype=np.float64)


@dataclass(frozen=True)
class CandidateA:
    """outcome = λ·wmean + (1-λ)·rp, λ = sigmoid(bias + β·standardized-features)."""

    beta: list[float]  # [bias, *feature weights]
    mean: list[float]
    std: list[float]
    l2: float
    features: tuple[str, ...] = _A_FEATURES

    def _lambda(self, rows: list[IssueData]) -> FloatArray:
        x = (_a_matrix(rows) - np.array(self.mean)) / np.array(self.std)
        design = np.column_stack([np.ones(len(rows)), x])
        return _sigmoid(design @ np.array(self.beta))

    def predict(self, rows: list[IssueData]) -> FloatArray:
        lam = self._lambda(rows)
        wmean = np.array([r.wmean for r in rows])
        rp = np.array([r.status_quo for r in rows])
        return np.asarray(lam * wmean + (1.0 - lam) * rp, dtype=np.float64)


def fit_candidate_a(train: list[IssueData], l2: float, iters: int = 4000) -> CandidateA:
    """Fit A on rp issues in ``train`` (issues without an rp are skipped — A needs a reference)."""
    rows = [r for r in train if r.rp is not None]
    raw = _a_matrix(rows)
    mean, std = _standardize(raw)
    x = (raw - mean) / std
    design = np.column_stack([np.ones(len(rows)), x])
    wmean = np.array([r.wmean for r in rows])
    rp = np.array([r.status_quo for r in rows])
    y = np.array([r.outcome for r in rows])
    reg_mask = np.array([0.0] + [1.0] * (design.shape[1] - 1))  # don't regularize the bias

    def grad(beta: FloatArray) -> FloatArray:
        z = design @ beta
        lam = _sigmoid(z)
        pred = lam * wmean + (1.0 - lam) * rp
        resid = pred - y
        dpred_dz = (wmean - rp) * lam * (1.0 - lam)
        g = (design.T @ (2.0 * resid * dpred_dz)) / len(rows)
        return np.asarray(g + 2.0 * l2 * reg_mask * beta, dtype=np.float64)

    beta = _adam(grad, np.zeros(design.shape[1]), iters=iters)
    return CandidateA(beta=beta.tolist(), mean=mean.tolist(), std=std.tolist(), l2=l2)


# --------------------------------------------------------------- Candidate B — regime-aware blend
_B_FEATURES = ("gini", "polarization", "rp_offset", "n_actors", "rule_cod")


def _b_matrix(rows: list[IssueData]) -> FloatArray:
    return np.array(
        [[r.gini, r.polarization, r.rp_offset, r.n_actors / 30.0, r.rule_cod] for r in rows],
        dtype=np.float64,
    )


@dataclass(frozen=True)
class CandidateB:
    """π = softmax(W·[1, features]); prediction = π_compromise·wmean + π_challenge·challenge +
    π_statusquo·rp. Regimes are ordered (compromise, challenge, status_quo)."""

    weights: list[list[float]]  # (3, n_features+1)
    mean: list[float]
    std: list[float]
    l2: float
    features: tuple[str, ...] = _B_FEATURES

    def _pi(self, rows: list[IssueData]) -> FloatArray:
        x = (_b_matrix(rows) - np.array(self.mean)) / np.array(self.std)
        design = np.column_stack([np.ones(len(rows)), x])
        logits = design @ np.array(self.weights).T
        logits = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        return np.asarray(exp / exp.sum(axis=1, keepdims=True), dtype=np.float64)

    def predict(self, rows: list[IssueData]) -> FloatArray:
        pi = self._pi(rows)
        comp = np.column_stack(
            [
                [r.wmean for r in rows],
                [r.challenge for r in rows],
                [r.status_quo for r in rows],
            ]
        )
        return np.asarray((pi * comp).sum(axis=1), dtype=np.float64)

    def mean_regime_weights(self, rows: list[IssueData]) -> dict[str, float]:
        pi = self._pi(rows).mean(axis=0)
        return {"compromise": float(pi[0]), "challenge": float(pi[1]), "status_quo": float(pi[2])}


def fit_candidate_b(train: list[IssueData], l2: float, iters: int = 4000) -> CandidateB:
    """Fit B on all ``train`` issues (softmax mixture of the three component estimates)."""
    raw = _b_matrix(train)
    mean, std = _standardize(raw)
    x = (raw - mean) / std
    design = np.column_stack([np.ones(len(train)), x])
    comp = np.column_stack(
        [
            [r.wmean for r in train],
            [r.challenge for r in train],
            [r.status_quo for r in train],
        ]
    )
    y = np.array([r.outcome for r in train])
    reg_mask = np.array([0.0] + [1.0] * (design.shape[1] - 1))
    n, k = len(train), design.shape[1]

    def grad(flat: FloatArray) -> FloatArray:
        w = flat.reshape(3, k)
        logits = design @ w.T
        logits = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        pi = exp / exp.sum(axis=1, keepdims=True)
        pred = (pi * comp).sum(axis=1)
        resid = pred - y
        # d pred / d logit_r = pi_r (comp_r - pred)
        dz = pi * (comp - pred[:, None])  # (n, 3)
        dloss_dz = 2.0 * resid[:, None] * dz / n  # (n, 3)
        g = dloss_dz.T @ design  # (3, k)
        g = g + 2.0 * l2 * reg_mask[None, :] * w
        return np.asarray(g.reshape(-1), dtype=np.float64)

    flat = _adam(grad, np.zeros(3 * k), iters=iters)
    return CandidateB(
        weights=flat.reshape(3, k).tolist(), mean=mean.tolist(), std=std.tolist(), l2=l2
    )


# --------------------------------------------------------------- scoring helpers
def mae(pred: FloatArray, rows: list[IssueData]) -> float:
    y = np.array([r.outcome for r in rows])
    return float(np.abs(pred - y).mean())


def compromise_pred(rows: list[IssueData]) -> FloatArray:
    return np.asarray([r.wmean for r in rows], dtype=np.float64)


# --------------------------------------------------------------- protocol: select on dev, TEST once
_L2_GRID = (0.0, 0.01, 0.1, 0.3, 1.0)


def select_candidates(
    data: list[IssueData], l2_grid: tuple[float, ...] = _L2_GRID
) -> tuple[CandidateA, CandidateB, dict[str, float]]:
    """Fit both candidates on TRAIN and pick each L2 by DEV MAE (TEST is never touched here)."""
    train = [d for d in data if d.split == "train"]
    dev = [d for d in data if d.split == "dev"]
    train_rp = [d for d in train if d.rp is not None]
    dev_rp = [d for d in dev if d.rp is not None]

    best_a: tuple[float, float, CandidateA] | None = None
    for l2 in l2_grid:
        cand = fit_candidate_a(train_rp, l2)
        dm = mae(cand.predict(dev_rp), dev_rp)
        if best_a is None or dm < best_a[0]:
            best_a = (dm, l2, cand)
    best_b: tuple[float, float, CandidateB] | None = None
    for l2 in l2_grid:
        cand_b = fit_candidate_b(train, l2)
        dm = mae(cand_b.predict(dev), dev)
        if best_b is None or dm < best_b[0]:
            best_b = (dm, l2, cand_b)
    assert best_a is not None and best_b is not None
    report = {
        "a_l2": best_a[1],
        "a_dev_mae": best_a[0],
        "a_dev_compromise": mae(compromise_pred(dev_rp), dev_rp),
        "b_l2": best_b[1],
        "b_dev_mae": best_b[0],
        "b_dev_compromise": mae(compromise_pred(dev), dev),
    }
    return best_a[2], best_b[2], report


def bootstrap_delta_ci(
    candidate_pred: FloatArray, rows: list[IssueData], *, seed: int, n_boot: int = 2000
) -> tuple[float, float, float]:
    """Paired bootstrap of MAE(candidate) - MAE(compromise); returns (point, ci_lo, ci_hi) at 95%.

    Same resampled indices for both models (paired), so the CI is of the *difference*. Deterministic
    under ``seed``. A CI entirely below 0 means the candidate beats the compromise baseline.
    """
    y = np.array([r.outcome for r in rows])
    ca = np.abs(candidate_pred - y)
    co = np.abs(compromise_pred(rows) - y)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(rows), size=(n_boot, len(rows)))
    deltas = ca[idx].mean(axis=1) - co[idx].mean(axis=1)
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return float(ca.mean() - co.mean()), float(lo), float(hi)


# --------------------------------------------------------------- full protocol + report artifact
@dataclass(frozen=True)
class CandidateResult:
    key: str  # --solver key, e.g. "gravity"
    name: str
    applies_to: str  # which TEST subset it is scored on
    l2: float
    dev_mae: float
    dev_compromise_mae: float
    n_test: int
    test_compromise_mae: float
    test_mae: float
    delta: float  # test_mae - test_compromise_mae (negative = beats)
    ci_lo: float
    ci_hi: float
    beats_compromise: bool
    extra: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SuccessorReport:
    dataset_sha256: str
    split_seed: int
    split_counts: dict[str, int]
    boot_seed: int
    candidates: list[CandidateResult]
    any_survivor: bool
    structural: list[CandidateResult] = field(default_factory=list)  # Phase C solvers (D41)


def run_successor_search(
    csv_path: Path = DEFAULT_CSV, boot_seed: int = BOOT_SEED
) -> tuple[SuccessorReport, CandidateA, CandidateB]:
    """The whole protocol: fit on train, tune on dev, score TEST once, with bootstrap CIs."""
    issues = load_deu_issues(csv_path, sourced_capability=True)
    split = load_committed_split()
    data = [build_issue_data(i, split[i.issue_id]) for i in issues]
    cand_a, cand_b, rep = select_candidates(data)

    test = [d for d in data if d.split == "test"]
    test_rp = [d for d in test if d.rp is not None]

    a_pred = cand_a.predict(test_rp)
    a_delta, a_lo, a_hi = bootstrap_delta_ci(a_pred, test_rp, seed=boot_seed)
    res_a = CandidateResult(
        key="gravity",
        name="Candidate A — status-quo gravity",
        applies_to="TEST rp-issues",
        l2=rep["a_l2"],
        dev_mae=rep["a_dev_mae"],
        dev_compromise_mae=rep["a_dev_compromise"],
        n_test=len(test_rp),
        test_compromise_mae=mae(compromise_pred(test_rp), test_rp),
        test_mae=mae(a_pred, test_rp),
        delta=a_delta,
        ci_lo=a_lo,
        ci_hi=a_hi,
        beats_compromise=a_delta < 0.0,
    )

    b_pred = cand_b.predict(test)
    b_delta, b_lo, b_hi = bootstrap_delta_ci(b_pred, test, seed=boot_seed)
    res_b = CandidateResult(
        key="regime",
        name="Candidate B — regime-aware settlement",
        applies_to="TEST (all)",
        l2=rep["b_l2"],
        dev_mae=rep["b_dev_mae"],
        dev_compromise_mae=rep["b_dev_compromise"],
        n_test=len(test),
        test_compromise_mae=mae(compromise_pred(test), test),
        test_mae=mae(b_pred, test),
        delta=b_delta,
        ci_lo=b_lo,
        ci_hi=b_hi,
        beats_compromise=b_delta < 0.0,
        extra={k: round(v, 4) for k, v in cand_b.mean_regime_weights(test).items()},
    )

    candidates = [res_a, res_b]
    structural = evaluate_structural_solvers(issues, split, boot_seed)
    return (
        SuccessorReport(
            dataset_sha256=dataset_sha256(csv_path),
            split_seed=SPLIT_SEED,
            split_counts=split_counts(split),
            boot_seed=boot_seed,
            candidates=candidates,
            any_survivor=any(c.beats_compromise for c in [*candidates, *structural]),
            structural=structural,
        ),
        cand_a,
        cand_b,
    )


# --------------------------------------------------------------- Phase C structural solvers (D41)
# Each is parameter-free (or fixed a priori) and scored ONCE on TEST, per docs/PHASE-C-GATE.md. The
# gate is the two-part rule: TEST MAE below compromise AND the 95% bootstrap CI entirely below 0.
_STRUCTURAL: tuple[tuple[str, str, str, bool], ...] = (
    ("challenge-qre", "challenge-qre — quantal response (D41.1)", "TEST (all)", False),
    ("pce", "pce — probabilistic Condorcet (D41.3)", "TEST (all)", False),
    ("nash", "nash — weighted Nash bargaining (D41.2)", "TEST rp-issues", True),
    ("nash-ks", "nash-ks — Kalai-Smorodinsky (D41.2)", "TEST rp-issues", True),
)


def _structural_pred(key: str, game: GameSpec, rp: float | None) -> float:
    """One structural solver's point forecast for a DEU issue (point-estimate game)."""
    cfg = SolverConfig(reference_point=rp)
    if key == "challenge-qre":
        return run_qre(game, cfg).forecast_median
    if key == "nash":
        return nash_forecast(game, cfg)
    if key == "nash-ks":
        return ks_forecast(game, cfg)
    return pce_forecast(game)


def _mae_on(
    issues: list[DEUIssue], split: dict[str, str], key: str, rp_only: bool, tag: str
) -> tuple[float, float, int]:
    """(solver MAE, compromise MAE, n) for one structural solver on a named split (tag)."""
    subset = [
        i
        for i in issues
        if split[i.issue_id] == tag and (i.reference_point is not None or not rp_only)
    ]
    if not subset:
        return float("nan"), float("nan"), 0
    y = np.array([i.outcome for i in subset], dtype=np.float64)
    preds = np.array([_structural_pred(key, i.game, i.reference_point) for i in subset])
    comp = np.array([compromise_estimate(i.game) for i in subset])
    return float(np.abs(preds - y).mean()), float(np.abs(comp - y).mean()), len(subset)


def evaluate_structural_solvers(
    issues: list[DEUIssue], split: dict[str, str], boot_seed: int = BOOT_SEED
) -> list[CandidateResult]:
    """Score every Phase C structural solver on TEST once, under the pre-registered gate (D41)."""
    results: list[CandidateResult] = []
    for key, name, applies, rp_only in _STRUCTURAL:
        test = [
            i
            for i in issues
            if split[i.issue_id] == "test" and (i.reference_point is not None or not rp_only)
        ]
        rows = [build_issue_data(i, "test") for i in test]
        preds = np.array([_structural_pred(key, i.game, i.reference_point) for i in test])
        delta, lo, hi = bootstrap_delta_ci(preds, rows, seed=boot_seed)
        dev_mae, dev_comp, _ = _mae_on(issues, split, key, rp_only, "dev")
        # Two-part gate: point improvement AND the whole 95% CI below zero (docs/PHASE-C-GATE.md).
        beats = delta < 0.0 and hi < 0.0
        results.append(
            CandidateResult(
                key=key,
                name=name,
                applies_to=applies,
                l2=0.0,
                dev_mae=dev_mae,
                dev_compromise_mae=dev_comp,
                n_test=len(rows),
                test_compromise_mae=mae(compromise_pred(rows), rows),
                test_mae=mae(preds, rows),
                delta=delta,
                ci_lo=lo,
                ci_hi=hi,
                beats_compromise=beats,
            )
        )
    return results


def build_issue_data_from_game(
    game: GameSpec, rp: float | None = None, procedure: str = "COD"
) -> IssueData:
    """Build the feature/component row for an arbitrary game (for the ``--solver`` candidates)."""
    return IssueData(
        issue_id="",
        split="",
        outcome=0.0,
        wmean=compromise_estimate(game),
        challenge=challenge_estimate(game),
        rp=rp,
        rule_cod=1.0 if procedure == "COD" else 0.0,
        gini=_gini(_weights(game)),
        herfindahl=_herfindahl(_weights(game)),
        polarization=_polarization(game),
        n_actors=len(game.actors),
    )


def predict_for_game(
    candidate: CandidateA | CandidateB, game: GameSpec, rp: float | None = None
) -> float:
    """A candidate's point forecast for one game (rp optional; if absent, status quo = wmean)."""
    return float(candidate.predict([build_issue_data_from_game(game, rp)])[0])


def load_candidate(kind: str) -> CandidateA | CandidateB:
    """Load a committed, train-fit candidate ('gravity' → A, 'regime' → B)."""
    data = json.loads((files("schelling.backtest") / f"deu3_candidate_{kind}.json").read_text())
    data.pop("kind", None)
    return CandidateA(**data) if kind == "gravity" else CandidateB(**data)


def forecast_candidate(
    game: GameSpec,
    kind: str,
    *,
    n_draws: int = 10_000,
    seed: int = 0,
    rp: float | None = None,
    out_dir: str | Path = "runs",
    write: bool = True,
) -> ForecastRecord:
    """A ForecastRecord for a candidate model ('gravity'|'regime'), MC over the game's ranges."""
    from schelling.mc.monte_carlo import MonteCarloResult, build_forecast_record, write_record
    from schelling.mc.sampling import derive_rng, sample_game
    from schelling.schemas.forecast import StoppingRule

    candidate = load_candidate(kind)
    cfg = SolverConfig(reference_point=rp)
    preds = np.array(
        [
            predict_for_game(candidate, sample_game(game, derive_rng(seed, i)), rp)
            for i in range(n_draws)
        ]
    )
    zeros = np.zeros(n_draws, dtype=np.int64)
    mc = MonteCarloResult(
        median_distribution=preds,
        mean_distribution=preds,
        rounds_executed=zeros,
        stopping_rules=(StoppingRule.CONVERGED,) * n_draws,
        n_draws=n_draws,
        seed=seed,
    )
    record = build_forecast_record(game, cfg, mc, [], model=kind)
    if write:
        write_record(record, out_dir)
    return record


def save_candidate(candidate: CandidateA | CandidateB, path: Path) -> None:
    """Persist a fitted (train-only) candidate to committed JSON for the ``--solver`` options."""
    kind = "gravity" if isinstance(candidate, CandidateA) else "regime"
    payload = {"kind": kind, **asdict(candidate)}
    payload.pop("features", None)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def leaderboard_markdown(report: SuccessorReport) -> str:
    """The living leaderboard section for BACKTEST.md (R1)."""
    lines = [
        "## Successor search — the leaderboard (Session R1)",
        "",
        f"Pre-registered 40/30/30 split (seed {report.split_seed}: train "
        f"{report.split_counts['train']}, dev {report.split_counts['dev']}, TEST "
        f"{report.split_counts['test']}), committed before any fitting; **TEST scored once**. Each "
        "candidate must beat the compromise weighted mean on the untouched TEST split; MAE deltas "
        f"carry a paired bootstrap 95% CI (seed {report.boot_seed}).",
        "",
        "| Candidate | Scored on | dev MAE (comp.) | TEST MAE | comp. MAE | Δ (95% CI) | beats? |",
        "|---|---|---|---:|---:|---|:--:|",
    ]
    for c in report.candidates:
        beats = "yes" if c.beats_compromise else "no"
        lines.append(
            f"| {c.name} | {c.applies_to} | {c.dev_mae:.2f} ({c.dev_compromise_mae:.2f}) | "
            f"{c.test_mae:.2f} | {c.test_compromise_mae:.2f} | "
            f"{c.delta:+.2f} [{c.ci_lo:+.2f}, {c.ci_hi:+.2f}] | {beats} |"
        )
    lines.append("")
    verdict = (
        "A candidate cleared the gate — see the ledger."
        if report.any_survivor
        else "**No candidate beats the compromise weighted mean on TEST.** Both point estimates "
        "are worse and both bootstrap CIs straddle zero — statistically indistinguishable from, "
        "but not better than, the mean. The compromise model remains the settlement model for "
        "DEU; nothing was sealed against the live US-Iran game. A negative result, pre-registered "
        "and honest."
    )
    lines.append(verdict)
    lines.append("")
    if report.structural:
        lines += _structural_section(report)
    return "\n".join(lines)


def _structural_section(report: SuccessorReport) -> list[str]:
    """The Phase C structural-solver leaderboard block (D41), under the same pre-registered gate."""
    lines = [
        "### Phase C structural solvers (Session 41)",
        "",
        "Parameter-free / a-priori-fixed solvers, scored **once** on the same committed TEST split "
        "under the pre-registered gate (docs/PHASE-C-GATE.md): a solver is **validated** only if "
        "its TEST MAE beats the compromise mean AND the 95% bootstrap CI lies entirely below 0. "
        "None is fitted, so there is no dev tuning; the dev column is shown for context only.",
        "",
        "| Solver | Scored on | dev MAE (comp.) | TEST MAE | comp. MAE | Δ (95% CI) | validated? |",
        "|---|---|---|---:|---:|---|:--:|",
    ]
    for c in report.structural:
        beats = "yes" if c.beats_compromise else "no (exploratory)"
        lines.append(
            f"| {c.name} | {c.applies_to} | {c.dev_mae:.2f} ({c.dev_compromise_mae:.2f}) | "
            f"{c.test_mae:.2f} | {c.test_compromise_mae:.2f} | "
            f"{c.delta:+.2f} [{c.ci_lo:+.2f}, {c.ci_hi:+.2f}] | {beats} |"
        )
    lines.append("")
    any_struct = any(c.beats_compromise for c in report.structural)
    if any_struct:
        lines.append("A structural solver cleared the gate — see the ledger.")
    else:
        lines.append(
            "**No structural solver beats the compromise mean on TEST.** As pre-registered and as "
            "the oracle ceiling (D11.0) predicted, each ships as an EXPLORATORY `--solver` option, "
            "never sealed against a live forecast — exactly as `gravity` and `regime` did. A "
            "negative result under a fixed rule is itself evidence."
        )
    lines.append("")
    return lines
