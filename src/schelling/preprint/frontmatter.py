"""Preprint front matter — the version-specific title-block fields (Session 55, D55).

Read from ``paper/preprint/front-matter.toml`` so a version bump is a config edit, not a code edit.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_FIELDS = (
    "author",
    "affiliation",
    "contact",
    "orcid",
    "dateline",
    "runhead",
    "keywords",
    "version_note",
)


@dataclass(frozen=True)
class FrontMatter:
    """The title-block fields for one preprint version."""

    author: str
    affiliation: str
    contact: str
    orcid: str  # ORCID iD, e.g. "0009-0004-5391-4030"
    dateline: str  # e.g. "Preprint · 2026-08-15 · v5"
    runhead: str  # the running header printed at the top of every page
    keywords: str  # "; "-separated
    version_note: str  # one-line "Changes since …" note


def load_front_matter(path: Path) -> FrontMatter:
    """Load the preprint front matter from a TOML file; raise ``ValueError`` on a missing field."""
    data = tomllib.loads(path.read_text())
    missing = [f for f in _FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        raise ValueError(f"preprint front matter {path} is missing: {', '.join(missing)}")
    return FrontMatter(**{f: str(data[f]) for f in _FIELDS})
