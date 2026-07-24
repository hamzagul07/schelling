"""Deep research mode (Session 38, D38).

``schelling research <situation.txt>`` runs iterative, multi-round evidence gathering — a broad
survey, then targeted searches for the coordinates the game needs but lacks, then contradiction
resolution — stopping when a round adds essentially no new information rather than after a fixed
number of searches. It writes a **research corpus**: every source with its retrieval date and
extracted claims, each claim tagged with a confidence level. ``formalize --corpus <dir>`` then
consumes that frozen corpus **offline**, so the draft is reproducible from a fixed evidence set, and
a committed confidence-to-width rule turns each coordinate's confidence into a range width —
contradictions widen the range across the disagreeing readings, never collapse to one side.
"""

from schelling.research.confidence import (
    ConfidenceRule,
    apply_confidence_widths,
    load_confidence_rule,
)
from schelling.research.corpus import load_corpus, write_corpus
from schelling.research.schemas import Claim, ResearchCorpus, ResearchSource, RoundLog

__all__ = [
    "Claim",
    "ConfidenceRule",
    "ResearchCorpus",
    "ResearchSource",
    "RoundLog",
    "apply_confidence_widths",
    "load_confidence_rule",
    "load_corpus",
    "write_corpus",
]
