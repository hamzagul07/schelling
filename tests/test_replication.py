"""THE replication gate (BUILD_PLAN §5).

Runs the solver on the BDM-1994 emission-standards fixture and checks the forecast against
the outcome Scholz et al. (2011) report reproducing, within the ±1.0 continuum-unit tolerance
the plan mandates. Until this is green (or the deviation is quantified in DECISIONS.md),
nothing downstream is trusted.

Reported outcomes (Scholz §7, pp. 27-28):
  * Scholz Table 2 steady-state median voter position (rounds 2-5): 9.9 years.
  * BDM's own stabilised dominant prediction: 9.05 years (actual resolution 8.833).
With the paper-faithful config (dynamic R, Q=1.0, risk on, adversary security, conflict =
uncertain = no move), the solver's converged median is ~9.53 — within ±1.0 of both. The
exact per-round Table-2 trajectory (8.4 → 9.9) is not bit-reproduced; see DECISIONS.md D2.7.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.schemas.question import GameSpec
from schelling.solver.config import RangeMode, SolverConfig
from schelling.solver.model import run
from schelling.solver.votes import game_mode_arrays, weighted_median

FIXTURES = Path(__file__).parent / "fixtures"

# Scholz-reproduced steady-state median (Table 2, rounds 2-5) and BDM's stabilised prediction.
SCHOLZ_STEADY_MEDIAN = 9.9
BDM_STABILISED = 9.05
TOLERANCE = 1.0


@pytest.fixture
def emission_game() -> GameSpec:
    data = json.loads((FIXTURES / "emission_standards.json").read_text())
    return GameSpec.model_validate(data)


@pytest.fixture
def replication_config() -> SolverConfig:
    """The paper-faithful configuration for the BDM-1994 replication (see DECISIONS.md D2.x)."""
    return SolverConfig(
        range_mode=RangeMode.DYNAMIC,  # positions are years 4-10 (D1.2 / D2.2)
        q=1.0,  # Scholz: "No value for Q was given. We chose Q=1.0." (p. 27)
        apply_risk=True,
        conflict_resolves=False,  # conflict = "uncertain outcome" = no move (A4 / D2.6)
        security_mode="adversary",  # §5 prose definition (A2 / D2.3)
    )


def test_initial_median_matches_hand_calculation(emission_game: GameSpec) -> None:
    """Sanity check: the round-0 weighted median of the raw table is 7.0 (hand-computed)."""
    positions, saliences, capabilities = game_mode_arrays(emission_game)
    cs = capabilities * saliences
    assert weighted_median(positions, cs) == pytest.approx(7.0)


def test_replication_forecast_within_tolerance(
    emission_game: GameSpec, replication_config: SolverConfig
) -> None:
    """THE gate: converged median forecast within ±1.0 of the reported outcome."""
    result = run(emission_game, replication_config)
    assert abs(result.forecast_median - SCHOLZ_STEADY_MEDIAN) <= TOLERANCE, (
        f"forecast median {result.forecast_median:.3f} not within {TOLERANCE} of "
        f"Scholz steady-state {SCHOLZ_STEADY_MEDIAN}"
    )
    # Also consistent with BDM's own stabilised prediction.
    assert abs(result.forecast_median - BDM_STABILISED) <= TOLERANCE


def test_replication_behaviour_is_consistent_with_scholz(
    emission_game: GameSpec, replication_config: SolverConfig
) -> None:
    """Round-count/behaviour consistent with Scholz: median rises from 7 to the high-cap bloc,
    stabilises, and — crucially — the mean stays in Scholz's ~7.4-7.6 band (the spread is
    preserved, not collapsed to a single point)."""
    result = run(emission_game, replication_config)

    # The median rises from the initial 7.0 toward the powerful position-10 bloc and stabilises.
    assert result.forecast_median >= 9.0
    assert result.rounds[0].weighted_median >= 8.5

    # Mean stays in Scholz's band for the first rounds (spread preserved).
    assert 7.0 <= result.rounds[0].weighted_mean <= 8.0

    # Positions do not all collapse to a single point (Scholz keep a spread; mean != median).
    final_positions = list(result.rounds[-1].positions.values())
    assert max(final_positions) - min(final_positions) > 3.0

    # Converges under our stopping rule well within the hard cap.
    from schelling.schemas.forecast import StoppingRule

    assert result.stopping_rule == StoppingRule.CONVERGED
    assert result.rounds_executed < replication_config.max_rounds


def test_replication_is_deterministic(
    emission_game: GameSpec, replication_config: SolverConfig
) -> None:
    """Same inputs -> byte-identical Forecast-relevant output (CLAUDE.md rule 2)."""
    a = run(emission_game, replication_config)
    b = run(emission_game, replication_config)
    assert a.model_dump_json() == b.model_dump_json()
