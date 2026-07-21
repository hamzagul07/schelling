"""Pydantic v2 data contracts (BUILD_PLAN §3).

These are the spine of the product. Field names freeze once the replication test is green;
change them only with a matching entry in DECISIONS.md.
"""

from schelling.schemas.forecast import (
    Assumption,
    DraftMetadata,
    Ensemble,
    ForecastRecord,
    RoundLog,
    SensitivityEntry,
    SolverResult,
)
from schelling.schemas.question import Continuum, GameSpec
from schelling.schemas.stakeholders import Actor, Evidence, TriangularEstimate

__all__ = [
    "Actor",
    "Assumption",
    "Continuum",
    "DraftMetadata",
    "Ensemble",
    "Evidence",
    "ForecastRecord",
    "GameSpec",
    "RoundLog",
    "SensitivityEntry",
    "SolverResult",
    "TriangularEstimate",
]
