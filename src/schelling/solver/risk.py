"""Risk propensity: security level -> risk basis R_i -> risk exponent r_i.

BUILD_PLAN §4 step 5; Scholz §5 (eqs. 32-34) and eq. 33. See DECISIONS.md D2.x.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


def security_levels(eu: FloatArray, mode: str = "adversary") -> FloatArray:
    """Security level of each actor (Scholz §5, p. 24; ambiguity A2).

    * ``"adversary"`` — ``Sec_i = sum_{j != i} E^j(U_ji)`` = column ``i`` of the EU matrix: the
      utility i's *adversaries* expect from challenging it (the §5 prose definition).
    * ``"own"`` — ``Sec_i = sum_{j != i} E^i(U_ij)`` = row ``i``: i's own EU of challenging others
      (a literal reading of the Appendix step-8 superscript ``E^i(...)``).

    The greater the sum, the less secure ``i`` is. Diagonal is 0, so no self-term to remove.
    """
    if mode == "own":
        return eu.sum(axis=1).astype(np.float64)  # sum over responders -> per challenger i
    return eu.sum(axis=0).astype(np.float64)  # sum over challengers -> per responder i


def risk_basis(security: FloatArray) -> FloatArray:
    """Risk basis ``R_i`` in [-1, 1] (Scholz eq. 32/34).

    ``R_i = (2 Sec_i - max_k Sec_k - min_k Sec_k) / (max_k Sec_k - min_k Sec_k)``. The most
    secure actor (lowest ``Sec``) maps to ``-1``; the least secure to ``+1``. If all securities
    are equal, the range is degenerate and every ``R_i = 0``.
    """
    s_max = float(np.max(security))
    s_min = float(np.min(security))
    spread = s_max - s_min
    if spread == 0.0:
        return np.zeros_like(security)
    return ((2.0 * security - s_max - s_min) / spread).astype(np.float64)


def risk_exponents(risk_basis_values: FloatArray) -> FloatArray:
    """Risk exponent ``r_i = (1 - R_i/3) / (1 + R_i/3)`` (Scholz eq. 33).

    Maps ``R_i in [-1, 1]`` to ``r_i in [0.5, 2]``: most secure (``R_i = -1``) -> ``r_i = 2``
    (risk-acceptant), least secure (``R_i = +1``) -> ``r_i = 0.5`` (risk-averse).
    """
    return ((1.0 - risk_basis_values / 3.0) / (1.0 + risk_basis_values / 3.0)).astype(np.float64)
