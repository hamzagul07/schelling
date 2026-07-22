"""Loader for the position-to-words vocabulary (``position_words.yaml``, Session 22, D22.4).

Turns a 0-100 continuum position or salience into an auditable phrase. Pure and deterministic; the
phrasing lives in the committed YAML, not in report strings, so it can be edited and reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

import yaml


@dataclass(frozen=True)
class Bucket:
    upto: float  # a value falls in this bucket when it is below ``upto``
    phrase: str


@dataclass(frozen=True)
class PositionVocab:
    position_thirds: list[Bucket]
    position_fifths: list[Bucket]
    salience_thirds: list[Bucket]


def _buckets(raw: list[dict[str, Any]]) -> list[Bucket]:
    return [Bucket(upto=float(b["upto"]), phrase=str(b["phrase"])) for b in raw]


@lru_cache(maxsize=1)
def load_vocab() -> PositionVocab:
    """Load the packaged vocabulary (cached; the YAML is immutable at runtime)."""
    text = (files("schelling.report") / "position_words.yaml").read_text()
    raw = cast("dict[str, Any]", yaml.safe_load(text))
    return PositionVocab(
        position_thirds=_buckets(raw["position"]["thirds"]),
        position_fifths=_buckets(raw["position"]["fifths"]),
        salience_thirds=_buckets(raw["salience"]["thirds"]),
    )


def phrase_for(value: float, buckets: list[Bucket]) -> str:
    """The phrase for ``value``: the first bucket it falls below, else the last (clamped)."""
    for b in buckets:
        if value < b.upto:
            return b.phrase
    return buckets[-1].phrase
