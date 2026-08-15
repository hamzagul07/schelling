"""The brief's committed prose, and the hard wall between prose and figures (Session 56, D56).

``docs/briefs/<slug>.md`` holds the standfirst, the beats, the commentary and the caveats as named
``## slot`` sections, with ``{{tags}}`` wherever a figure belongs. :func:`resolve_prose` substitutes
each tag from the artifact-sourced values and FAILS the build if any tag is unresolved or any
required slot is missing — the same discipline as the dossier narrative. The prose never carries a
figure of its own; every number it shows arrives through a tag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SLOT = re.compile(r"^##[ \t]+([a-z0-9-]+)[ \t]*$", re.MULTILINE)
_TAG = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

# Every section the renderer expects; a missing one fails the build (the prose is incomplete).
REQUIRED_SLOTS: tuple[str, ...] = (
    "eyebrow",
    "headline",
    "standfirst",
    "beat-sealed",
    "beat-resolved",
    "beat-graded",
    "landed-title",
    "landed-note",
    "chart-caption",
    "scores-title",
    "scores-note",
    "shows-title",
    "commentary-pull",
    "commentary-body",
    "caveats-pull",
    "caveats",
    "footer-note",
    "source-label",
)


class BriefProseError(ValueError):
    """Raised on a malformed brief prose file — a missing slot or an unresolved ``{{tag}}``."""


@dataclass(frozen=True)
class BriefProse:
    """The parsed ``## slot`` sections of a brief's prose file, before tag resolution."""

    sections: dict[str, str]


def parse_prose(md_text: str) -> BriefProse:
    """Split a brief prose file into its ``## slot`` sections (text trimmed, order irrelevant)."""
    marks = list(_SLOT.finditer(md_text))
    sections: dict[str, str] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md_text)
        sections[m.group(1)] = md_text[m.end() : end].strip()
    return BriefProse(sections)


def resolve_prose(prose: BriefProse, values: dict[str, str]) -> dict[str, str]:
    """Resolve every ``{{tag}}`` in every required slot; raise on a missing slot or unknown tag.

    Returns ``{slot: resolved-text}``. This is the hard wall: an unresolved tag can never reach the
    page — the build fails loudly instead of shipping a ``{{...}}`` or a silent blank.
    """
    missing = [slot for slot in REQUIRED_SLOTS if slot not in prose.sections]
    if missing:
        raise BriefProseError(f"brief prose is missing required slot(s): {', '.join(missing)}")

    resolved: dict[str, str] = {}
    for slot in REQUIRED_SLOTS:
        unknown: list[str] = []

        def _sub(m: re.Match[str], _unknown: list[str] = unknown) -> str:
            key = m.group(1)
            if key not in values:
                _unknown.append(key)
                return m.group(0)
            return values[key]

        text = _TAG.sub(_sub, prose.sections[slot])
        if unknown:
            raise BriefProseError(
                f"slot '{slot}' has unresolved tag(s): "
                + ", ".join("{{" + k + "}}" for k in unknown)
                + " — no such artifact figure."
            )
        resolved[slot] = text
    return resolved
