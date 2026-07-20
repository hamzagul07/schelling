"""The concepts-library firewall (CLAUDE.md rule 6 / rule f).

Defense-in-depth behind the prompt-level rule: after the model returns a draft, verify that no
content unique to the retrieved concept library (template cards + index chunks) has leaked into
a factual field (an actor identity, an evidence source/note, or an assumption). Facts must trace
to the supplied situation text or sources — never to the index.

Detection is deterministic and low-false-positive: a leak is a 3-word shingle (or a distinctive
alphanumeric code) that appears in the *concepts* text and the draft's factual surface but NOT
in the supplied facts. Verbatim game-theory vocabulary in a template rationale is fine — the
rationale is not part of the factual surface. See DECISIONS.md D5.2.
"""

from __future__ import annotations

import re

from schelling.formalizer.schemas import DraftExtraction, DraftGameSpec

_WORD = re.compile(r"[a-z0-9]+")
_SHINGLE_N = 3


class IndexLeakageError(Exception):
    """Raised when concept-library content leaks into a factual field of a draft."""

    def __init__(self, leaks: list[str]) -> None:
        self.leaks = leaks
        preview = ", ".join(repr(x) for x in leaks[:5])
        super().__init__(
            f"concepts-library content leaked into factual fields ({len(leaks)}): {preview}"
        )


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _shingles(tokens: list[str], n: int = _SHINGLE_N) -> set[str]:
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _is_code(token: str) -> bool:
    """A distinctive alphanumeric code (has BOTH a letter and a digit), e.g. ``b52``, ``sk9``.

    Deliberately excludes bare numbers (``20``, ``2035``) — numbers are ubiquitous and their
    presence in both the concept library and a draft is not a leak. Multi-word factual leaks
    are caught by the 3-gram shingle check instead.
    """
    return any(c.isalpha() for c in token) and any(c.isdigit() for c in token)


def factual_surface(draft: DraftExtraction | DraftGameSpec) -> str:
    """The text of a draft that must trace to supplied facts (actors, evidence, assumptions).

    Deliberately excludes ``template_classification`` — that is where the concept library is
    *supposed* to be cited.
    """
    parts: list[str] = []
    for actor in draft.game.actors:
        parts.append(actor.id)
        parts.append(actor.name)
        for ev in actor.evidence:
            parts.extend([ev.source, ev.note])
    for assumption in draft.assumptions:
        parts.extend([assumption.statement, assumption.why])
    return "\n".join(parts)


def find_leaks(
    draft: DraftExtraction | DraftGameSpec,
    allowed_text: str,
    concepts_text: str,
) -> list[str]:
    """Return concept-library fragments that leaked into the draft's factual surface.

    ``allowed_text`` is the supplied situation + sources (the only legitimate provenance for
    facts); ``concepts_text`` is the retrieved template cards + index chunks.
    """
    allowed_tokens = set(_tokens(allowed_text))
    allowed_shingles = _shingles(_tokens(allowed_text))
    concept_tokens = _tokens(concepts_text)

    # Content unique to the concept library (not present in the supplied facts).
    concept_only_shingles = _shingles(concept_tokens) - allowed_shingles
    concept_only_codes = {t for t in concept_tokens if _is_code(t)} - allowed_tokens

    surface_tokens = _tokens(factual_surface(draft))
    surface_shingles = _shingles(surface_tokens)
    surface_token_set = set(surface_tokens)

    leaks = (concept_only_shingles & surface_shingles) | (concept_only_codes & surface_token_set)
    return sorted(leaks)


def assert_no_leakage(
    draft: DraftExtraction | DraftGameSpec,
    allowed_text: str,
    concepts_text: str,
) -> None:
    """Raise :class:`IndexLeakageError` if any concept-library content reached a factual field."""
    leaks = find_leaks(draft, allowed_text, concepts_text)
    if leaks:
        raise IndexLeakageError(leaks)
