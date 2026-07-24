"""Shapley-Shubik and Banzhaf power indices for a weighted voting game (Session 40, D40.2).

An **evidence aid**, never an automatic assignment. In a weighted voting game each player casts a
bloc of ``weight`` votes and a coalition wins when its weight reaches the ``quota``. A player's
*power* is not its weight but how often it is **pivotal** — the classic result that a small weight
can be a dummy (zero power) and equal weights can hold unequal power. This module computes:

* **Shapley-Shubik** index: over all orderings of the players, the fraction in which a player is the
  one who tips a losing coalition into a winning one. Sums to 1.
* **Banzhaf** index (normalized): a player's share of all *swings* — coalitions that win with the
  player and lose without it.

Both use the same swing test; they differ only in how a swing is weighted (Shapley by the
permutation's probability, Banzhaf by a plain count). Small games use **exact enumeration**
of all ``2^n`` coalitions; above ``exact_max_n`` (default 20, since exact cost is exponential) the
Shapley index is estimated by **Monte-Carlo permutation sampling** and the Banzhaf index by
random-coalition sampling, each **seeded** (CLAUDE.md rule 2) and reported with a standard error.

Output is a table of indices printed with the rule and quota used, for a human to cite in a draft
(the formalizer may cite it as a *source* for a capability value in a voting body). It must never
silently write a capability — see ``schelling power`` in the CLI, which only prints.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

SHAPLEY_SHUBIK = "shapley-shubik"
BANZHAF = "banzhaf"
EXACT = "exact"
MONTE_CARLO = "monte-carlo"

DEFAULT_EXACT_MAX_N = 20  # above this, exact 2^n enumeration is too expensive — sample instead
DEFAULT_SAMPLES = 200_000


@dataclass(frozen=True)
class PowerResult:
    """One index over a weighted voting game, with the method and (if sampled) a standard error."""

    rule: str  # SHAPLEY_SHUBIK | BANZHAF
    labels: list[str]
    weights: list[float]
    quota: float
    indices: list[float]  # aligned with labels; sums to 1
    method: str  # EXACT | MONTE_CARLO
    samples: int  # 0 for exact
    standard_error: list[float] | None  # per-player SE (MONTE_CARLO only)
    seed: int

    @property
    def dummies(self) -> list[str]:
        """Players with (essentially) zero power — a weight that never swings a vote."""
        return [lab for lab, v in zip(self.labels, self.indices, strict=True) if v <= 1e-9]


def _merge_blocs(
    weights: Sequence[float], labels: Sequence[str], blocs: Sequence[Sequence[str]] | None
) -> tuple[list[float], list[str]]:
    """Collapse each bloc of labels into one player whose weight is the bloc's summed weight.

    A bloc votes as a unit, so it is a single player in the game. Unblocked players stay individual.
    Bloc order is preserved first (in input order), then the remaining singletons in input order.
    """
    if not blocs:
        return list(weights), list(labels)
    index_of = {lab: i for i, lab in enumerate(labels)}
    used: set[str] = set()
    out_w: list[float] = []
    out_l: list[str] = []
    for bloc in blocs:
        members = list(bloc)
        if not members:
            continue
        for m in members:
            if m not in index_of:
                raise ValueError(f"bloc member {m!r} is not a player")
            if m in used:
                raise ValueError(f"player {m!r} appears in more than one bloc")
            used.add(m)
        out_w.append(sum(weights[index_of[m]] for m in members))
        out_l.append("+".join(members))
    for i, lab in enumerate(labels):
        if lab not in used:
            out_w.append(weights[i])
            out_l.append(lab)
    return out_w, out_l


def _coalition_weights(weights: list[float]) -> np.ndarray:
    """Total weight of each of the ``2^n`` coalitions, indexed by bitmask (DP, one add each)."""
    n = len(weights)
    wsum = np.zeros(1 << n, dtype=np.float64)
    for mask in range(1, 1 << n):
        low = mask & (-mask)
        i = low.bit_length() - 1
        wsum[mask] = wsum[mask ^ low] + weights[i]
    return wsum


def _exact(weights: list[float], quota: float) -> tuple[list[float], list[float]]:
    """Exact Shapley-Shubik and normalized Banzhaf indices by enumerating all coalitions.

    A player ``i`` *swings* a coalition ``S`` (with ``i in S``) when ``w(S) >= quota`` but
    ``w(S) - w_i < quota``. Shapley weights each swing by ``(s-1)!(n-s)!/n!`` (its share of
    orderings); Banzhaf counts each swing as 1, then normalizes by the total swing count.
    """
    n = len(weights)
    fact = [math.factorial(k) for k in range(n + 1)]
    wsum = _coalition_weights(weights)
    ss = [0.0] * n
    swings = [0] * n
    for mask in range(1 << n):
        total = wsum[mask]
        if total < quota:
            continue  # a losing coalition has no swings
        s = int(mask.bit_count())
        weight = fact[s - 1] * fact[n - s] / fact[n]
        for i in range(n):
            if mask & (1 << i) and total - weights[i] < quota:
                swings[i] += 1
                ss[i] += weight
    total_swings = sum(swings)
    bz = [c / total_swings for c in swings] if total_swings else [0.0] * n
    return ss, bz


def _mc_shapley(
    weights: list[float], quota: float, samples: int, rng: np.random.Generator
) -> tuple[list[float], list[float]]:
    """Monte-Carlo Shapley-Shubik: the pivot rate over random orderings, with a binomial SE."""
    n = len(weights)
    w = np.asarray(weights, dtype=np.float64)
    pivotal = np.zeros(n, dtype=np.int64)
    for _ in range(samples):
        order = rng.permutation(n)
        cum = np.cumsum(w[order])
        pivot_pos = int(np.searchsorted(cum, quota))  # first index reaching the quota
        if pivot_pos < n:
            pivotal[order[pivot_pos]] += 1
    p = pivotal / samples
    se = np.sqrt(p * (1.0 - p) / samples)
    return p.tolist(), se.tolist()


def _mc_banzhaf(
    weights: list[float], quota: float, samples: int, rng: np.random.Generator
) -> tuple[list[float], list[float]]:
    """Monte-Carlo Banzhaf: each player's swing rate over random coalitions of the others.

    For player ``i`` a random subset of the *other* players is drawn (each in with prob 1/2); ``i``
    swings when that subset loses but wins once ``i`` joins. The normalized index divides each
    swing rate by the total; the SE is the binomial SE of the raw swing rate, carried through.
    """
    n = len(weights)
    w = np.asarray(weights, dtype=np.float64)
    swing = np.zeros(n, dtype=np.int64)
    for _ in range(samples):
        members = rng.random(n) < 0.5  # a random coalition of all players
        base = float(w[members].sum())
        for i in range(n):
            without = base - w[i] if members[i] else base
            if without < quota <= without + w[i]:
                swing[i] += 1
    rate = swing / samples
    total = rate.sum()
    idx = (rate / total) if total > 0 else np.zeros(n)
    se_raw = np.sqrt(rate * (1.0 - rate) / samples)
    se = (se_raw / total) if total > 0 else se_raw
    return idx.tolist(), se.tolist()


def compute_power(
    weights: Sequence[float],
    quota: float,
    *,
    labels: Sequence[str] | None = None,
    blocs: Sequence[Sequence[str]] | None = None,
    seed: int = 0,
    samples: int = DEFAULT_SAMPLES,
    exact_max_n: int = DEFAULT_EXACT_MAX_N,
) -> dict[str, PowerResult]:
    """Both power indices for a weighted voting game; exact for small ``n``, else seeded MC (D40.2).

    ``labels`` name the players (default ``P1..Pn``); ``blocs`` groups labels that vote as a unit.
    Returns ``{"shapley-shubik": PowerResult, "banzhaf": PowerResult}``.
    """
    labels = list(labels) if labels is not None else [f"P{i + 1}" for i in range(len(weights))]
    if len(labels) != len(weights):
        raise ValueError("labels and weights must have the same length")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    if quota <= 0:
        raise ValueError("quota must be positive")
    w, lab = _merge_blocs(weights, labels, blocs)
    n = len(w)
    total_weight = sum(w)
    if quota > total_weight:
        raise ValueError(f"quota {quota} exceeds total weight {total_weight}: no coalition can win")
    if n <= exact_max_n:
        ss, bz = _exact(w, quota)
        method, used_samples, ss_se, bz_se = EXACT, 0, None, None
    else:
        rng = np.random.default_rng(seed)
        ss, ss_se = _mc_shapley(w, quota, samples, rng)
        bz, bz_se = _mc_banzhaf(w, quota, samples, rng)
        method, used_samples = MONTE_CARLO, samples
    return {
        SHAPLEY_SHUBIK: PowerResult(
            SHAPLEY_SHUBIK, lab, w, quota, ss, method, used_samples, ss_se, seed
        ),
        BANZHAF: PowerResult(BANZHAF, lab, w, quota, bz, method, used_samples, bz_se, seed),
    }


def format_power(results: dict[str, PowerResult]) -> str:
    """Render both indices as a plain-text table with the rule, quota, and method stated (AID)."""
    ss = results[SHAPLEY_SHUBIK]
    bz = results[BANZHAF]
    total_weight = sum(ss.weights)
    width = max((len(lab) for lab in ss.labels), default=6)
    lines = [
        f"Weighted voting power — quota {ss.quota:g} of {total_weight:g} total weight "
        f"({ss.method}"
        + (f", {ss.samples} samples, seed {ss.seed}" if ss.method == MONTE_CARLO else "")
        + ")",
        "An evidence AID, not a capability assignment. Cite it; never let it write a value.",
        f"  {'player':<{width}}  {'weight':>7}  {'Shapley-Shubik':>16}  {'Banzhaf':>12}",
    ]
    for i, lab in enumerate(ss.labels):
        ss_cell = f"{ss.indices[i]:.4f}"
        bz_cell = f"{bz.indices[i]:.4f}"
        if ss.standard_error is not None and bz.standard_error is not None:
            ss_cell += f" ±{ss.standard_error[i]:.4f}"
            bz_cell += f" ±{bz.standard_error[i]:.4f}"
        lines.append(f"  {lab:<{width}}  {ss.weights[i]:>7g}  {ss_cell:>16}  {bz_cell:>12}")
    if ss.dummies:
        lines.append(f"  dummies (zero power): {', '.join(ss.dummies)}")
    return "\n".join(lines)
