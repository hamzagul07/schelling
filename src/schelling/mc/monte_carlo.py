"""Monte Carlo runner + ForecastRecord emission (BUILD_PLAN §6, and §3's audit artifact).

``N`` triangular draws, each solved deterministically with a seed derived from the master
seed and the draw index; aggregate into the outcome distribution, CI80, and convergence
statistics; wire the complete :class:`ForecastRecord` (distribution, sensitivity, seed,
config, inputs hash, engine git SHA) to ``runs/``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from schelling.mc.sampling import derive_rng, sample_game
from schelling.mc.sensitivity import tornado
from schelling.schemas.forecast import (
    Assumption,
    DraftMetadata,
    Ensemble,
    ForecastRecord,
    SensitivityEntry,
    StoppingRule,
)
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

DEFAULT_DRAWS = 10_000
_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class MonteCarloResult:
    """Raw per-draw outputs of a Monte Carlo run (pure; no aggregation opinions baked in)."""

    median_distribution: FloatArray  # converged headline median per draw
    mean_distribution: FloatArray  # converged weighted mean per draw
    rounds_executed: IntArray  # rounds per draw
    stopping_rules: tuple[StoppingRule, ...]  # which rule fired per draw
    n_draws: int
    seed: int


def run_monte_carlo(
    game: GameSpec,
    config: SolverConfig | None = None,
    n_draws: int = DEFAULT_DRAWS,
    seed: int = 0,
) -> MonteCarloResult:
    """Solve ``n_draws`` triangular draws deterministically and collect per-draw outputs.

    Draw ``i`` uses ``derive_rng(seed, i)``; a point-estimate game yields identical draws
    (zero variance). The round loop is plain Python but the contest math is vectorized, so
    10k draws finish well under the §6 60-second budget.
    """
    cfg = config or SolverConfig()
    medians = np.empty(n_draws, dtype=np.float64)
    means = np.empty(n_draws, dtype=np.float64)
    rounds = np.empty(n_draws, dtype=np.int64)
    stops: list[StoppingRule] = []
    for i in range(n_draws):
        result = run(sample_game(game, derive_rng(seed, i)), cfg)
        medians[i] = result.forecast_median
        means[i] = result.forecast_mean
        rounds[i] = result.rounds_executed
        stops.append(result.stopping_rule)
    return MonteCarloResult(
        median_distribution=medians,
        mean_distribution=means,
        rounds_executed=rounds,
        stopping_rules=tuple(stops),
        n_draws=n_draws,
        seed=seed,
    )


def ci80(distribution: FloatArray) -> tuple[float, float]:
    """The 80% credible interval — 10th and 90th percentiles of a distribution."""
    return float(np.percentile(distribution, 10)), float(np.percentile(distribution, 90))


def convergence_stats(mc: MonteCarloResult) -> dict[str, float]:
    """Aggregate convergence behaviour across draws (rounds distribution, stopping-rule rates)."""
    n = float(mc.n_draws)
    converged = sum(1 for s in mc.stopping_rules if s == StoppingRule.CONVERGED)
    capped = sum(1 for s in mc.stopping_rules if s == StoppingRule.ROUND_CAP)
    return {
        "n_draws": n,
        "converged_fraction": converged / n,
        "round_cap_fraction": capped / n,
        "rounds_mean": float(np.mean(mc.rounds_executed)),
        "rounds_median": float(np.median(mc.rounds_executed)),
        "rounds_min": float(np.min(mc.rounds_executed)),
        "rounds_max": float(np.max(mc.rounds_executed)),
    }


def engine_version() -> str:
    """The engine's git commit SHA (deterministic within a commit), or ``"unknown"``."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def inputs_hash(game: GameSpec, config: SolverConfig) -> str:
    """SHA-256 of the canonical (GameSpec + SolverConfig) JSON — the run's content address."""
    payload = {
        "game": game.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_forecast_record(
    game: GameSpec,
    config: SolverConfig,
    mc: MonteCarloResult,
    sensitivity: list[SensitivityEntry],
    created_at: str | None = None,
    assumptions: list[Assumption] | None = None,
    formalizer_metadata: DraftMetadata | None = None,
    live_searched: bool = False,
) -> ForecastRecord:
    """Assemble the complete :class:`ForecastRecord` from a Monte Carlo run.

    The headline statistics live in the ``ensemble`` block and summarize the per-draw
    converged **median**: ``ensemble.median`` (central estimate), ``ensemble.mean`` (expected
    outcome), ``ensemble.p10``/``p90`` (CI80). See D4.2. ``run_id`` is derived from the inputs
    hash and seed, so identical inputs address the same record file deterministically. When the
    game came from a formalized draft, its ``assumptions`` and formalize metadata are carried
    through so the provenance chain is end-to-end (D6.8).
    """
    dist = np.sort(mc.median_distribution)
    hashed = inputs_hash(game, config)
    run_id = f"{game.question_id}-mc{mc.n_draws}-s{mc.seed}-{hashed[:12]}"
    p10, p90 = ci80(mc.median_distribution)
    # Deterministic mode-game solve -> the per-round median trajectory embedded in the record.
    mode_result = run(game, config)
    trajectory = [rl.weighted_median for rl in mode_result.rounds]
    return ForecastRecord(
        question_id=game.question_id,
        run_id=run_id,
        engine_version=engine_version(),
        inputs_hash=hashed,
        seed=mc.seed,
        solver_config=config.model_dump(mode="json"),
        created_at=created_at,
        ensemble=Ensemble(
            median=float(np.median(dist)),
            mean=float(np.mean(dist)),
            p10=p10,
            p90=p90,
            n_draws=mc.n_draws,
        ),
        game=game,
        median_trajectory=trajectory,
        assumptions=list(assumptions or []),
        formalizer_metadata=formalizer_metadata,
        live_searched=live_searched,
        outcome_distribution=[float(v) for v in dist],
        convergence_stats=convergence_stats(mc),
        sensitivity=sensitivity,
    )


def write_record(record: ForecastRecord, out_dir: str | Path = "runs") -> Path:
    """Write ``record`` to ``<out_dir>/<run_id>.json`` and return the path."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.run_id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def forecast(
    game: GameSpec,
    config: SolverConfig | None = None,
    n_draws: int = DEFAULT_DRAWS,
    seed: int = 0,
    out_dir: str | Path = "runs",
    created_at: str | None = None,
    write: bool = True,
    assumptions: list[Assumption] | None = None,
    formalizer_metadata: DraftMetadata | None = None,
    live_searched: bool = False,
) -> ForecastRecord:
    """Run Monte Carlo + sensitivity, build the ForecastRecord, and (by default) persist it.

    This is the one entry point that emits a complete audit artifact for a question. Pass a
    draft's ``assumptions`` and ``formalizer_metadata`` to carry its provenance into the record.
    """
    cfg = config or SolverConfig()
    mc = run_monte_carlo(game, cfg, n_draws=n_draws, seed=seed)
    sensitivity = tornado(game, cfg)
    record = build_forecast_record(
        game,
        cfg,
        mc,
        sensitivity,
        created_at=created_at,
        assumptions=assumptions,
        formalizer_metadata=formalizer_metadata,
        live_searched=live_searched,
    )
    if write:
        write_record(record, out_dir)
    return record
