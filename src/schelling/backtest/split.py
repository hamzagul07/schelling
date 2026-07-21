"""Train / dev / TEST split for the DEU successor search (Session R1).

Research discipline: the split is assigned deterministically from a seed and **committed before any
model is fitted**, so the held-out TEST scores can be trusted (`deu3_split.json`). Each issue id is
ordered by a seeded hash and cut 40/30/30 — exact counts, order-independent, reproducible. The TEST
split is scored exactly once, at the very end.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from importlib.resources import files

SPLIT_SEED = 20260721
FRACTIONS = (0.40, 0.30, 0.30)  # train / dev / test
_SPLIT_RESOURCE = "deu3_split.json"


def _rank_key(issue_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{issue_id}".encode()).hexdigest()


def make_split(
    issue_ids: Iterable[str],
    seed: int = SPLIT_SEED,
    fractions: tuple[float, float, float] = FRACTIONS,
) -> dict[str, str]:
    """Assign each issue id to 'train'/'dev'/'test' by seeded-hash order, cut at ``fractions``."""
    ordered = sorted(set(issue_ids), key=lambda i: _rank_key(i, seed))
    n = len(ordered)
    n_train = round(n * fractions[0])
    n_dev = round(n * fractions[1])
    labels: dict[str, str] = {}
    for k, issue_id in enumerate(ordered):
        if k < n_train:
            labels[issue_id] = "train"
        elif k < n_train + n_dev:
            labels[issue_id] = "dev"
        else:
            labels[issue_id] = "test"
    return labels


def load_committed_split() -> dict[str, str]:
    """Load the committed split assignment (issue_id -> split) — the pre-registered partition."""
    text = (files("schelling.backtest") / _SPLIT_RESOURCE).read_text()
    data = json.loads(text)
    return dict(data["assignment"])


def split_counts(assignment: dict[str, str]) -> dict[str, int]:
    counts = {"train": 0, "dev": 0, "test": 0}
    for label in assignment.values():
        counts[label] += 1
    return counts
