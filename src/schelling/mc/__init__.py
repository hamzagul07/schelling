"""Monte Carlo + sensitivity layer (BUILD_PLAN §6)."""

from schelling.mc.monte_carlo import (
    MonteCarloResult,
    build_forecast_record,
    ci80,
    convergence_stats,
    engine_sha,
    forecast,
    inputs_hash,
    run_monte_carlo,
    write_record,
)
from schelling.mc.sampling import derive_rng, sample_game, sample_triangular
from schelling.mc.sensitivity import format_tornado, tornado

__all__ = [
    "MonteCarloResult",
    "build_forecast_record",
    "ci80",
    "convergence_stats",
    "derive_rng",
    "engine_sha",
    "forecast",
    "format_tornado",
    "inputs_hash",
    "run_monte_carlo",
    "sample_game",
    "sample_triangular",
    "tornado",
    "write_record",
]
