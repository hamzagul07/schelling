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

from schelling.mc.correlated import salience_cholesky, sample_game_correlated
from schelling.mc.sampling import derive_rng, sample_game
from schelling.mc.sensitivity import tornado
from schelling.schemas.forecast import (
    AnalogPanel,
    Assumption,
    DraftMetadata,
    Ensemble,
    FetchedSource,
    ForecastRecord,
    SensitivityEntry,
    StoppingRule,
)
from schelling.schemas.question import GameSpec
from schelling.solver.config import SolverConfig
from schelling.solver.model import run
from schelling.solver.nash import ks_forecast, nash_forecast
from schelling.solver.pce import pce_forecast
from schelling.solver.qre import run_qre
from schelling.solver.registry import CURRENT_ENGINE_VERSION
from schelling.solver.votes import weighted_mean

# Forecasting models the MC layer can run per draw (D10.5).
MODEL_CHALLENGE = "challenge"  # the BDM bargaining solver (headline = converged weighted median)
MODEL_COMPROMISE = "compromise"  # the capability x salience weighted mean (Van den Bos / DEU)
# Phase C solvers (Session 41, D41): each a NEW option routed by engine v1's dispatch below — the
# challenge and compromise numerical paths are untouched (D39.2 gate stays green).
MODEL_CHALLENGE_QRE = "challenge-qre"  # quantal-response challenge model (D41.1)
MODEL_NASH = "nash"  # weighted Nash bargaining (D41.2)
MODEL_NASH_KS = "nash-ks"  # Kalai-Smorodinsky bargaining (D41.2)
MODEL_PCE = "pce"  # probabilistic Condorcet election, the KTAB method (D41.3)
# Every forecasting model this build ships, for CLI validation / listing.
KNOWN_MODELS = (
    MODEL_CHALLENGE,
    MODEL_COMPROMISE,
    MODEL_CHALLENGE_QRE,
    MODEL_NASH,
    MODEL_NASH_KS,
    MODEL_PCE,
)

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


def _compromise_forecast(game: GameSpec) -> float:
    """The compromise model: the capability x salience weighted mean of positions (D10.5)."""
    positions = np.array([a.position.mode for a in game.actors], dtype=np.float64)
    weights = np.array([a.capability.mode * a.salience.mode for a in game.actors], dtype=np.float64)
    return weighted_mean(positions, weights)


def run_monte_carlo(
    game: GameSpec,
    config: SolverConfig | None = None,
    n_draws: int = DEFAULT_DRAWS,
    seed: int = 0,
    model: str = MODEL_CHALLENGE,
    correlated: bool = False,
) -> MonteCarloResult:
    """Solve ``n_draws`` triangular draws deterministically and collect per-draw outputs.

    Draw ``i`` uses ``derive_rng(seed, i)``; a point-estimate game yields identical draws
    (zero variance). ``model`` selects the per-draw forecast: the challenge (BDM) solver's
    converged median, or the compromise weighted mean (D10.5). The round loop is plain Python but
    the contest math is vectorized, so 10k draws finish well under the §6 60-second budget.

    ``correlated`` opts into the Gaussian-copula sampler (salience correlated within coalitions,
    D41.4) instead of the default independent per-field draws; the marginals are unchanged.
    """
    cfg = config or SolverConfig()
    medians = np.empty(n_draws, dtype=np.float64)
    means = np.empty(n_draws, dtype=np.float64)
    rounds = np.empty(n_draws, dtype=np.int64)
    stops: list[StoppingRule] = []
    chol = salience_cholesky(game) if correlated else None
    for i in range(n_draws):
        rng = derive_rng(seed, i)
        draw = (
            sample_game_correlated(game, rng, chol) if chol is not None else sample_game(game, rng)
        )
        if model == MODEL_COMPROMISE:
            value = _compromise_forecast(draw)
            medians[i] = value
            means[i] = value
            rounds[i] = 0
            stops.append(StoppingRule.CONVERGED)
        elif model == MODEL_CHALLENGE_QRE:  # D41.1 — quantal-response challenge
            qre = run_qre(draw, cfg)
            medians[i] = qre.forecast_median
            means[i] = qre.forecast_mean
            rounds[i] = qre.rounds_executed
            stops.append(qre.stopping_rule)
        elif model in (
            MODEL_NASH,
            MODEL_NASH_KS,
            MODEL_PCE,
        ):  # D41.2 / D41.3 — closed-form settlements
            if model == MODEL_NASH:
                value = nash_forecast(draw, cfg)
            elif model == MODEL_NASH_KS:
                value = ks_forecast(draw, cfg)
            else:
                value = pce_forecast(draw)
            medians[i] = value
            means[i] = value
            rounds[i] = 0
            stops.append(StoppingRule.CONVERGED)
        else:  # challenge (unchanged default path — D39.2 depends on this staying identical)
            result = run(draw, cfg)
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


def engine_sha() -> str:
    """The engine's git commit SHA (deterministic within a commit), or ``"unknown"``.

    Provenance only — the *numerical* engine version is the integer
    ``ForecastRecord.engine_version`` (D39), which selects the solve path ``schelling verify``
    re-runs."""
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


CURRENT_HASH_VERSION = "v2"
# Canonicalization epochs (D18.1), newest first — verify tries these in order so legacy records
# reproduce. v2 (Session 10, D10.4) added SolverConfig.reference_point to the hashed config; v1
# records predate that field, so recomputing v1 drops it. Same inputs + same era -> same hash.
KNOWN_HASH_VERSIONS = ("v2", "v1")
_V1_DROPPED_CONFIG_FIELDS = frozenset({"reference_point"})


def inputs_hash(
    game: GameSpec, config: SolverConfig, *, hash_version: str = CURRENT_HASH_VERSION
) -> str:
    """SHA-256 of the canonical (GameSpec + SolverConfig) JSON — the run's content address.

    ``resolution_rubric`` is excluded (D17.1): it is grading metadata, not a solver input, so it
    must not change a forecast or its content-address — and excluding it keeps the hashes of
    records sealed before the rubric existed byte-stable.

    ``hash_version`` selects the canonicalization epoch (D18.1). ``v2`` (current) hashes the full
    config; ``v1`` drops the reference-point field, which did not exist when the earliest records
    were sealed, so their stored hashes reproduce under ``v1`` without touching one sealed byte.
    """
    config_dump = config.model_dump(mode="json")
    if hash_version == "v1":
        config_dump = {k: v for k, v in config_dump.items() if k not in _V1_DROPPED_CONFIG_FIELDS}
    elif hash_version != CURRENT_HASH_VERSION:
        raise ValueError(f"unknown hash_version {hash_version!r} (known: {KNOWN_HASH_VERSIONS})")
    payload = {
        "game": game.model_dump(
            mode="json", exclude={"resolution_rubric", "non_voting_actor_ids", "short_names"}
        ),
        "config": config_dump,
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
    sources_fetched: list[FetchedSource] | None = None,
    model: str = MODEL_CHALLENGE,
    analog_panel: AnalogPanel | None = None,
    sampling: str = "independent",
) -> ForecastRecord:
    """Assemble the complete :class:`ForecastRecord` from a Monte Carlo run.

    The headline statistics live in the ``ensemble`` block and summarize the per-draw
    converged **median**: ``ensemble.median`` (central estimate), ``ensemble.mean`` (expected
    outcome), ``ensemble.p10``/``p90`` (CI80). See D4.2. ``run_id`` is derived from the inputs
    hash and seed, so identical inputs address the same record file deterministically. When the
    game came from a formalized draft, its ``assumptions`` and formalize metadata are carried
    through so the provenance chain is end-to-end (D6.8). ``model`` records which forecaster
    produced the ensemble (D10.5).
    """
    dist = np.sort(mc.median_distribution)
    hashed = inputs_hash(game, config)
    tag = "" if model == MODEL_CHALLENGE else f"-{model}"
    run_id = f"{game.question_id}{tag}-mc{mc.n_draws}-s{mc.seed}-{hashed[:12]}"
    p10, p90 = ci80(mc.median_distribution)
    # The challenge model embeds its per-round median trajectory; the compromise model has none.
    if model == MODEL_CHALLENGE:
        trajectory = [rl.weighted_median for rl in run(game, config).rounds]
    else:
        trajectory = []
    return ForecastRecord(
        question_id=game.question_id,
        run_id=run_id,
        engine_version=CURRENT_ENGINE_VERSION,
        engine_sha=engine_sha(),
        inputs_hash=hashed,
        seed=mc.seed,
        model=model,
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
        sources_fetched=list(sources_fetched or []),
        analog_panel=analog_panel,
        outcome_distribution=[float(v) for v in dist],
        convergence_stats=convergence_stats(mc),
        sensitivity=sensitivity,
        sampling=sampling,
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
    sources_fetched: list[FetchedSource] | None = None,
    model: str = MODEL_CHALLENGE,
    analog_panel: AnalogPanel | None = None,
    correlated: bool = False,
) -> ForecastRecord:
    """Run Monte Carlo + sensitivity, build the ForecastRecord, and (by default) persist it.

    This is the one entry point that emits a complete audit artifact for a question. Pass a
    draft's ``assumptions`` and ``formalizer_metadata`` to carry its provenance into the record.
    ``model`` selects the challenge (BDM) or compromise (weighted-mean) forecaster (D10.5).
    ``correlated`` opts into the copula sampler (D41.4); it defaults off, so existing runs are
    byte-identical, and the choice is recorded in ``ForecastRecord.sampling``.
    """
    cfg = config or SolverConfig()
    mc = run_monte_carlo(game, cfg, n_draws=n_draws, seed=seed, model=model, correlated=correlated)
    # The tornado re-solves the challenge model; it is not meaningful for the compromise mean.
    sensitivity = tornado(game, cfg) if model == MODEL_CHALLENGE else []
    record = build_forecast_record(
        game,
        cfg,
        mc,
        sensitivity,
        created_at=created_at,
        assumptions=assumptions,
        formalizer_metadata=formalizer_metadata,
        live_searched=live_searched,
        sources_fetched=sources_fetched,
        model=model,
        analog_panel=analog_panel,
        sampling="correlated" if correlated else "independent",
    )
    if write:
        write_record(record, out_dir)
    return record
