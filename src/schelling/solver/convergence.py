"""Stopping rule — our upgrade over the original's convergence ambiguity.

BUILD_PLAN §4 step 8: stop when (a) the forecast median moves < ``epsilon`` continuum units
for ``patience`` consecutive rounds, or (b) a hard cap of ``max_rounds``. Never silently
truncate — ``model.py`` records which rule fired and the full per-round trajectory.
"""

from __future__ import annotations

from collections.abc import Sequence


def has_converged(median_trajectory: Sequence[float], epsilon: float, patience: int) -> bool:
    """True when the last ``patience`` consecutive median moves are all ``< epsilon``.

    ``median_trajectory`` is the end-of-round median for every round so far (in order). Needs at
    least ``patience + 1`` medians to measure ``patience`` moves.
    """
    if patience < 1:
        raise ValueError(f"patience must be >= 1, got {patience}")
    if len(median_trajectory) < patience + 1:
        return False
    recent = median_trajectory[-(patience + 1) :]
    moves = [abs(recent[k + 1] - recent[k]) for k in range(patience)]
    return all(move < epsilon for move in moves)
