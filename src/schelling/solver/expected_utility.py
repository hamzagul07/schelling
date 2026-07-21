"""Basic utilities, prevail probability, and the expected utility of challenging.

BUILD_PLAN §4 step 4; Scholz §3 (eqs. 5-24) and §4 (eqs. 30-31). See
``docs/papers/scholz_extract.md`` and DECISIONS.md D2.x for interpretive choices.

All functions are pure and scalar (one dyad at a time); ``rounds.py`` vectorizes the loop.
The challenger's own risk exponent ``r`` parameterizes every utility term.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class BasicUtilities:
    """The five basic utilities for a challenger, at a fixed risk exponent (Scholz eqs. 15-24)."""

    u_s: float  # success (eq. 15)
    u_f: float  # failure (eq. 16)
    u_b: float  # better, no-challenge (eq. 22)
    u_w: float  # worse, no-challenge (eq. 23)
    u_sq: float  # status quo (eq. 24)


def basic_utilities(
    x_i: float,
    x_j: float,
    mu: float,
    cont_range: float,
    r: float,
    reference_point: float | None = None,
) -> BasicUtilities:
    """Compute the five basic utilities for challenger ``i`` against ``j`` (Scholz eqs. 15-24).

    ``mu`` is the current median-voter position; ``cont_range`` is ``R = x_max - x_min``. Each
    bracketed base lies in ``[0, 1]`` (because every normalized distance is ``<= 1``), so raising
    to a fractional ``r`` stays real — this is exactly the scaling Scholz preserve with the 2s
    and 4s (p. 21). When ``reference_point`` is set, the status-quo utility is the utility of an
    outcome at that point (distance-scaled), not the constant "no move" value (D10.4).
    """
    if cont_range <= 0.0:
        raise ValueError(f"cont_range must be positive, got {cont_range}")
    d_ij = abs(x_i - x_j) / cont_range
    d_bw = (abs(x_i - mu) + abs(x_i - x_j)) / cont_range
    if reference_point is None:
        u_sq = 2.0 - 4.0 * (0.5) ** r
    else:
        d_sq = min(abs(x_i - reference_point) / cont_range, 1.0)
        u_sq = 2.0 - 4.0 * (0.5 + 0.5 * d_sq) ** r
    return BasicUtilities(
        u_s=2.0 - 4.0 * (0.5 - 0.5 * d_ij) ** r,
        u_f=2.0 - 4.0 * (0.5 + 0.5 * d_ij) ** r,
        u_b=2.0 - 4.0 * (0.5 - 0.25 * d_bw) ** r,
        u_w=2.0 - 4.0 * (0.5 + 0.25 * d_bw) ** r,
        u_sq=u_sq,
    )


def prevail_probability(
    x_i: float, x_j: float, positions: FloatArray, cs_weights: FloatArray
) -> float:
    """Probability ``P^i`` that ``i`` prevails over ``j`` in the bilateral contest (Scholz eq. 31).

    ``P^i = sum_{k: k supports i} c_k s_k (|x_k - x_j| - |x_k - x_i|) / sum_k c_k s_k | ... |``.
    A voter ``k`` supports ``i`` when it is closer to ``x_i`` than to ``x_j`` (arg > 0). If every
    voter is equidistant (denominator 0) the contest is a toss-up and we return 0.5. This is a
    ratio of vote sums, so any common scaling of ``c_k s_k`` cancels (D1.1 guard holds).
    """
    arg = np.abs(positions - x_j) - np.abs(positions - x_i)
    denom = float(np.sum(cs_weights * np.abs(arg)))
    if denom == 0.0:
        return 0.5
    numer = float(np.sum(cs_weights[arg > 0.0] * arg[arg > 0.0]))
    return numer / denom


def t_indicator(x_i: float, x_j: float, mu: float) -> float:
    """The no-challenge better/worse selector ``T`` (Scholz figs. 1-4, p. 22).

    ``T = 1`` iff the median is closer to ``i`` than ``j`` is (``|x_i - mu| < |x_i - x_j|``) — j's
    expected move to the median then improves i (cases 1 & 3A); otherwise ``T = 0`` (cases 2 &
    3B). Irrelevant when ``Q = 1`` (the no-challenge term vanishes).
    """
    return 1.0 if abs(x_i - mu) < abs(x_i - x_j) else 0.0


def expected_utility(
    challenger: int,
    responder: int,
    positions: FloatArray,
    saliences: FloatArray,
    cs_weights: FloatArray,
    mu: float,
    cont_range: float,
    r_challenger: float,
    q: float,
    reference_point: float | None = None,
) -> float:
    """Expected utility to ``challenger`` of challenging ``responder`` (Scholz eqs. 5-7 / 25).

    ``E = s_resp (P U_s + (1-P) U_f) + (1 - s_resp) U_s  -  Q U_sq  -  (1-Q)(T U_b + (1-T) U_w)``
    where ``s_resp`` is the *responder's* salience normalized to [0, 1] (eq. 6; A1) and ``P`` is
    the challenger's prevail probability. Positive ``E`` means the challenger expects to gain.
    """
    x_c = float(positions[challenger])
    x_r = float(positions[responder])
    s_resp = float(saliences[responder]) / 100.0  # normalize 0-100 salience to a [0,1] weight
    p = prevail_probability(x_c, x_r, positions, cs_weights)
    u = basic_utilities(x_c, x_r, mu, cont_range, r_challenger, reference_point)
    t = t_indicator(x_c, x_r, mu)
    e_challenge = s_resp * (p * u.u_s + (1.0 - p) * u.u_f) + (1.0 - s_resp) * u.u_s
    e_no_challenge = q * u.u_sq + (1.0 - q) * (t * u.u_b + (1.0 - t) * u.u_w)
    return e_challenge - e_no_challenge


def eu_matrix(
    positions: FloatArray,
    saliences: FloatArray,
    cs_weights: FloatArray,
    mu: float,
    cont_range: float,
    r: FloatArray,
    q: float,
    reference_point: float | None = None,
) -> FloatArray:
    """Matrix ``EU[i, j]`` = expected utility to challenger ``i`` of challenging responder ``j``.

    Fully vectorized (numpy broadcasting) — equivalent to calling :func:`expected_utility` for
    every off-diagonal cell, but ~orders of magnitude faster for Monte Carlo (BUILD_PLAN §6:
    "vectorize contests with numpy"). Uses each challenger's own risk exponent ``r[i]`` (per
    row). Diagonal is 0 (no self-challenge). A parity test pins it to the scalar version.
    """
    if cont_range <= 0.0:
        raise ValueError(f"cont_range must be positive, got {cont_range}")
    x = positions
    dist = np.abs(x[:, None] - x[None, :])  # dist[i, j] = |x_i - x_j|

    # Prevail probability P[i, j] (Scholz eq. 31): arg[i, j, k] = |x_k - x_j| - |x_k - x_i|.
    dt = dist.T  # dt[m, k] = |x_k - x_m|
    arg = dt[None, :, :] - dt[:, None, :]  # (i, j, k)
    cs = cs_weights[None, None, :]
    numer = np.where(arg > 0.0, arg, 0.0) * cs
    denom = np.abs(arg) * cs
    num_sum = numer.sum(axis=2)
    den_sum = denom.sum(axis=2)
    p = np.where(den_sum > 0.0, num_sum / np.where(den_sum > 0.0, den_sum, 1.0), 0.5)

    # Basic utilities (Scholz eqs. 15-24), each challenger i's risk exponent on its row.
    d_ij = dist / cont_range
    d_mu = np.abs(x - mu) / cont_range  # per challenger i
    d_bw = d_mu[:, None] + d_ij
    r_col = r[:, None]
    u_s = 2.0 - 4.0 * np.maximum(0.5 - 0.5 * d_ij, 0.0) ** r_col
    u_f = 2.0 - 4.0 * np.maximum(0.5 + 0.5 * d_ij, 0.0) ** r_col
    u_b = 2.0 - 4.0 * np.maximum(0.5 - 0.25 * d_bw, 0.0) ** r_col
    u_w = 2.0 - 4.0 * np.maximum(0.5 + 0.25 * d_bw, 0.0) ** r_col
    if reference_point is None:
        u_sq = (2.0 - 4.0 * (0.5) ** r)[:, None]  # per challenger i: status quo = "no move"
    else:
        d_sq = np.minimum(np.abs(x - reference_point) / cont_range, 1.0)  # per i, capped at edge
        u_sq = (2.0 - 4.0 * (0.5 + 0.5 * d_sq) ** r)[:, None]  # status quo = outcome at rp (D10.4)

    t = (np.abs(x[:, None] - mu) < dist).astype(np.float64)  # T[i, j]
    s_resp = saliences[None, :] / 100.0  # responder j's salience, normalized

    e_challenge = s_resp * (p * u_s + (1.0 - p) * u_f) + (1.0 - s_resp) * u_s
    e_no_challenge = q * u_sq + (1.0 - q) * (t * u_b + (1.0 - t) * u_w)
    eu = e_challenge - e_no_challenge
    np.fill_diagonal(eu, 0.0)
    return eu.astype(np.float64)
