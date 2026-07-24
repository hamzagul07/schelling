"""The committed confidence-to-width rule and its deterministic application (D38.4).

The rule lives in ``confidence.yaml`` (a config file, not prose) so it can be cited and audited.
:func:`apply_confidence_widths` is a pure function of the draft and the corpus: it rewrites each
actor coordinate's range width from that coordinate's confidence, keeping the mode the formalizer
chose. A contested coordinate spans its recorded disagreeing readings — the contradiction widens the
range, it is never silently resolved to one side.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

import yaml

from schelling.formalizer.schemas import DraftGameSpec
from schelling.research.schemas import Confidence, ResearchCorpus
from schelling.schemas.stakeholders import TriangularEstimate

_PARAMS = ("position", "salience", "capability")


@dataclass(frozen=True)
class ConfidenceRule:
    """Half-widths (on the 0-100 continuum) per confidence level; contested spans its readings."""

    established: float
    reported: float
    inferred: float
    contested_min_half_width: float

    def half_width(self, confidence: Confidence) -> float:
        """The symmetric half-width for a non-contested confidence (falls back to inferred)."""
        return {
            "established": self.established,
            "reported": self.reported,
            "inferred": self.inferred,
        }.get(confidence, self.inferred)


@lru_cache(maxsize=1)
def load_confidence_rule() -> ConfidenceRule:
    """Load the packaged confidence-to-width rule (cached; the YAML is immutable at runtime)."""
    text = (files("schelling.research") / "confidence.yaml").read_text()
    raw = cast("dict[str, Any]", yaml.safe_load(text))
    return ConfidenceRule(
        established=float(raw["established"]),
        reported=float(raw["reported"]),
        inferred=float(raw["inferred"]),
        contested_min_half_width=float(raw["contested_min_half_width"]),
    )


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _widen(
    mode: float, confidence: Confidence, readings: list[float], rule: ConfidenceRule
) -> TriangularEstimate:
    """The triangular range for one coordinate: mode kept, width set by confidence (D38.4)."""
    if confidence == "contested":
        pts = [mode, *readings]
        lo, hi = min(pts), max(pts)
        # a contested range is at least contested_min_half_width to each side of the mode
        lo = min(lo, mode - rule.contested_min_half_width)
        hi = max(hi, mode + rule.contested_min_half_width)
    else:
        hw = rule.half_width(confidence)
        lo, hi = mode - hw, mode + hw
    lo, hi = _clamp(lo), _clamp(hi)
    mode = _clamp(mode)
    return TriangularEstimate(low=min(lo, mode), mode=mode, high=max(hi, mode))


def apply_confidence_widths(
    draft: DraftGameSpec, corpus: ResearchCorpus, rule: ConfidenceRule | None = None
) -> DraftGameSpec:
    """Rewrite every actor coordinate's range width from the corpus confidence (pure, D38.4).

    The formalizer's mode is kept; the half-width comes from the coordinate's derived confidence
    (``<actor_id>.<param>``). A coordinate with no claim is ``inferred`` (widest). Contested
    coordinates span their recorded readings. Nothing else in the draft changes.
    """
    rule = rule or load_confidence_rule()
    conf = corpus.coordinate_confidence()
    readings = corpus.coordinate_readings()
    new_actors = []
    for actor in draft.game.actors:
        updates: dict[str, TriangularEstimate] = {}
        for param in _PARAMS:
            coord = f"{actor.id}.{param}"
            c: Confidence = conf.get(coord, "inferred")
            est: TriangularEstimate = getattr(actor, param)
            updates[param] = _widen(est.mode, c, readings.get(coord, []), rule)
        new_actors.append(actor.model_copy(update=updates))
    new_game = draft.game.model_copy(update={"actors": new_actors})
    return draft.model_copy(update={"game": new_game})
