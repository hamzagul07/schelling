"""Loader for the committed report figure palette (``palette.yaml``, Session 23, D23.4).

Colours live in the YAML, never hardcoded in ``svg.py`` or ``render.py``; edit the map and every
figure follows. Pure and deterministic.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

import yaml

from schelling.report.svg import Palette


@lru_cache(maxsize=1)
def load_palette() -> Palette:
    """Load the packaged figure palette (cached; the YAML is immutable at runtime)."""
    text = (files("schelling.report") / "palette.yaml").read_text()
    raw = cast("dict[str, Any]", yaml.safe_load(text))
    return Palette(
        low_half=str(raw["low_half"]),
        high_half=str(raw["high_half"]),
        modal_stroke=str(raw["modal_stroke"]),
        median_pointer=str(raw["median_pointer"]),
        ci_bracket=str(raw["ci_bracket"]),
        non_voting_flag=str(raw["non_voting_flag"]),
    )
