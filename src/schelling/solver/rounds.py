"""One round: median -> (two-pass) EU -> octants -> offers -> synchronous position update.

BUILD_PLAN §4 step 7; Scholz Appendix steps 3-12. See DECISIONS.md D2.x.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.expected_utility import eu_matrix
from schelling.solver.octants import Offer, Relation, classify
from schelling.solver.risk import risk_basis, risk_exponents, security_levels
from schelling.solver.votes import weighted_mean, weighted_median

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class RoundOutcome:
    """Everything one round produced — enough to populate a full ``RoundLog``."""

    new_positions: FloatArray
    mu_used: float  # median-voter position used for this round's utilities (start-of-round)
    mean_used: float  # start-of-round weighted mean
    r_exponents: FloatArray  # risk exponent per actor used for the second-pass EU
    relations: dict[tuple[int, int], Relation]  # (i, j) i<j -> relation
    accepted_offers: dict[int, float] = field(default_factory=dict)  # mover index -> new position


def continuum_range(positions: FloatArray, config: SolverConfig) -> float:
    """Continuum range ``R`` for the utility formulas (DECISIONS.md D1.2 / D2.2).

    ``FIXED`` -> ``config.fixed_range``; ``DYNAMIC`` -> ``max - min`` of current positions.
    A degenerate dynamic range (all positions equal) returns 0.0; callers treat that as
    "nothing left to move".
    """
    if config.range_mode == RangeMode.FIXED:
        return config.fixed_range
    return float(np.max(positions) - np.min(positions))


def _round_eu(
    positions: FloatArray,
    saliences: FloatArray,
    cs_weights: FloatArray,
    mu: float,
    cont_range: float,
    config: SolverConfig,
) -> tuple[FloatArray, FloatArray]:
    """Compute the (optionally risk-adjusted) EU matrix and the risk exponents used.

    First pass with ``r = 1``; if ``apply_risk``, derive ``r_i`` from first-pass security and
    recompute (Appendix steps 8-10). Returns ``(eu_second_pass, r_exponents)``.
    """
    n = positions.size
    rp = config.reference_point
    r_ones = np.ones(n, dtype=np.float64)
    eu_first = eu_matrix(positions, saliences, cs_weights, mu, cont_range, r_ones, config.q, rp)
    if not config.apply_risk:
        return eu_first, r_ones
    r_vals = risk_exponents(risk_basis(security_levels(eu_first, config.security_mode)))
    eu_second = eu_matrix(positions, saliences, cs_weights, mu, cont_range, r_vals, config.q, rp)
    return eu_second, r_vals


def _select_offer(offers: list[Offer], positions: FloatArray) -> dict[int, float]:
    """Each actor accepts the most-enforceable offer made to it (Scholz §6.2; A4).

    "Those better able to enforce their wishes than others can make their proposals stick"
    (p. 251): the offer from the proposer with the highest expected utility (``enforceability``)
    wins. Only "given equally enforceable proposals" does the actor "move the least that it
    can" — so ties in enforceability break to the smallest movement, then to the smaller target
    position for full determinism.
    """
    best: dict[int, Offer] = {}
    for offer in offers:
        if offer.mover is None or offer.new_position is None:
            continue
        mover = offer.mover
        incumbent = best.get(mover)
        if incumbent is None or _prefer(offer, incumbent, float(positions[mover])):
            best[mover] = offer
    return {
        mover: float(offer.new_position)
        for mover, offer in best.items()
        if offer.new_position is not None
    }


def _prefer(candidate: Offer, incumbent: Offer, current: float) -> bool:
    """True if ``candidate`` should replace ``incumbent`` as a mover's accepted offer."""
    if candidate.enforceability != incumbent.enforceability:
        return candidate.enforceability > incumbent.enforceability
    cand_move = abs((candidate.new_position or current) - current)
    inc_move = abs((incumbent.new_position or current) - current)
    if cand_move != inc_move:
        return cand_move < inc_move
    return (candidate.new_position or current) < (incumbent.new_position or current)


def run_round(
    positions: FloatArray,
    saliences: FloatArray,
    cs_weights: FloatArray,
    config: SolverConfig,
) -> RoundOutcome:
    """Execute one round and return the resulting positions and full audit detail."""
    mu = weighted_median(positions, cs_weights)
    mean_used = weighted_mean(positions, cs_weights)
    cont_range = continuum_range(positions, config)
    n = positions.size

    # Degenerate range (all positions coincide): nothing can move.
    if cont_range <= 0.0:
        return RoundOutcome(
            new_positions=positions.copy(),
            mu_used=mu,
            mean_used=mean_used,
            r_exponents=np.ones(n, dtype=np.float64),
            relations={},
        )

    eu, r_vals = _round_eu(positions, saliences, cs_weights, mu, cont_range, config)

    offers: list[Offer] = []
    relations: dict[tuple[int, int], Relation] = {}
    for i in range(n):
        for j in range(i + 1, n):
            offer = classify(
                a=float(eu[i, j]),
                b=float(eu[j, i]),
                i=i,
                j=j,
                x_i=float(positions[i]),
                x_j=float(positions[j]),
                conflict_resolves=config.conflict_resolves,
            )
            relations[(i, j)] = offer.relation
            offers.append(offer)

    accepted = _select_offer(offers, positions)
    new_positions = positions.copy()
    for mover, target in accepted.items():
        new_positions[mover] = target

    return RoundOutcome(
        new_positions=new_positions,
        mu_used=mu,
        mean_used=mean_used,
        r_exponents=r_vals,
        relations=relations,
        accepted_offers=accepted,
    )
