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
    x_i: float, x_j: float, mu: float, cont_range: float, r: float
) -> BasicUtilities:
    """Compute the five basic utilities for challenger ``i`` against ``j`` (Scholz eqs. 15-24).

    ``mu`` is the current median-voter position; ``cont_range`` is ``R = x_max - x_min``. Each
    bracketed base lies in ``[0, 1]`` (because every normalized distance is ``<= 1``), so raising
    to a fractional ``r`` stays real — this is exactly the scaling Scholz preserve with the 2s
    and 4s (p. 21).
    """
    if cont_range <= 0.0:
        raise ValueError(f"cont_range must be positive, got {cont_range}")
    d_ij = abs(x_i - x_j) / cont_range
    d_bw = (abs(x_i - mu) + abs(x_i - x_j)) / cont_range
    return BasicUtilities(
        u_s=2.0 - 4.0 * (0.5 - 0.5 * d_ij) ** r,
        u_f=2.0 - 4.0 * (0.5 + 0.5 * d_ij) ** r,
        u_b=2.0 - 4.0 * (0.5 - 0.25 * d_bw) ** r,
        u_w=2.0 - 4.0 * (0.5 + 0.25 * d_bw) ** r,
        u_sq=2.0 - 4.0 * (0.5) ** r,
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
    u = basic_utilities(x_c, x_r, mu, cont_range, r_challenger)
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
) -> FloatArray:
    """Matrix ``M[c, r]`` = expected utility to challenger ``c`` of challenging responder ``r``.

    Diagonal is 0 (no self-challenge). Uses each challenger's own risk exponent ``r[c]``.
    """
    n = positions.size
    m = np.zeros((n, n), dtype=np.float64)
    for c in range(n):
        for resp in range(n):
            if c == resp:
                continue
            m[c, resp] = expected_utility(
                c, resp, positions, saliences, cs_weights, mu, cont_range, float(r[c]), q
            )
    return m
