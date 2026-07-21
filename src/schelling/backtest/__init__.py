"""The DEU backtest harness (Phase 2, Session 9).

Ingest the DEU dataset (Decision-making in the European Union) into normalized issues, run every
issue through the deterministic solver and naive baselines, and score |forecast - actual| against
the real decision outcomes. Search is never involved — this is a frozen historical benchmark
(CLAUDE.md rule 7).
"""

from schelling.backtest.deu import ACTOR_NAMES, dataset_sha256, load_deu_issues
from schelling.backtest.harness import (
    median_position_forecast,
    run_backtest,
    solver_forecast,
    weighted_mean_forecast,
)

__all__ = [
    "ACTOR_NAMES",
    "dataset_sha256",
    "load_deu_issues",
    "median_position_forecast",
    "run_backtest",
    "solver_forecast",
    "weighted_mean_forecast",
]
