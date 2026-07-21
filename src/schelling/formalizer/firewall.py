"""The concepts-library firewall (CLAUDE.md rule 6 / rule f).

Defense-in-depth behind the prompt-level rule: after the model returns a draft, verify that no
content unique to the retrieved concept library (template cards + index chunks) has leaked into
a factual field (an actor identity, an evidence source/note, or an assumption). Facts must trace
to the supplied situation text or sources — never to the index.

Detection is deterministic and calibrated to catch *specific factual content* while ignoring
*analysis vocabulary* (D6.5): a leak is (a) a distinctive **4-word** shingle — at least two of
its tokens are neither stopwords nor canonical game-theory terms — present in the concepts text
and a factual field but absent from the supplied facts, or (b) a distinctive alphanumeric code
(letter *and* digit). The theory whitelist is drawn from ``templates.yaml`` (card names +
solution_concept terms), so phrases like "the shadow of the future" are treated as analysis
language, not fact. Fail-closed: any leak raises :class:`IndexLeakageError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

import yaml

from schelling.formalizer.schemas import DraftExtraction, DraftGameSpec

_WORD = re.compile(r"[a-z0-9]+")
_SHINGLE_N = 4  # phrase-match shingles are 4-grams (D6.5b)
_MIN_CONTENT_TOKENS = 2  # a shingle needs >= 2 non-stopword, non-theory tokens to be distinctive

# Common English function words — stopword-heavy phrases are not distinctive factual content.
_STOPWORD_TEXT = (
    "a an the of to in on at by for and or but nor so yet as is are was were be been being "
    "this that these those it its their his her our your my i you he she they we them us him "
    "with from into over under above below between among about against during before after "
    "not no yes if then than when where while who whom which what how why all any some each "
    "more most much many few less least very can will would should could may might must do "
    "does did done have has had having up down out off only own same such other another"
)
_STOPWORDS: frozenset[str] = frozenset(_STOPWORD_TEXT.split())


@dataclass(frozen=True)
class Leak:
    """One detected leak: the offending phrase/token and where it was found."""

    phrase: str
    location: str  # e.g. "actor 'germany' evidence[0].note"


class IndexLeakageError(Exception):
    """Raised when concept-library content leaks into a factual field of a draft."""

    def __init__(
        self, leaks: list[Leak], draft: DraftExtraction | DraftGameSpec | None = None
    ) -> None:
        self.leaks = leaks
        self.draft = draft
        preview = "; ".join(f"{leak.phrase!r} in {leak.location}" for leak in leaks[:5])
        super().__init__(
            f"concepts-library content leaked into factual fields ({len(leaks)}): {preview}"
        )

    def phrases(self) -> list[str]:
        """The distinct offending phrases, for feeding back into a rephrase retry."""
        seen: dict[str, None] = {}
        for leak in self.leaks:
            seen.setdefault(leak.phrase, None)
        return list(seen)


@lru_cache(maxsize=1)
def _theory_vocab() -> frozenset[str]:
    """Canonical game-theory vocabulary from templates.yaml (card names + solution_concept)."""
    text = (files("schelling.knowledge") / "templates.yaml").read_text()
    cards = cast("list[dict[str, Any]]", yaml.safe_load(text)["templates"])
    tokens: set[str] = set()
    for card in cards:
        tokens.update(_tokens(str(card.get("name", ""))))
        tokens.update(_tokens(str(card.get("solution_concept", ""))))
    return frozenset(tokens)


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _shingles(tokens: list[str], n: int = _SHINGLE_N) -> set[str]:
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _is_code(token: str) -> bool:
    """A distinctive alphanumeric code (letter AND digit), e.g. ``b52`` — not a bare number."""
    return any(c.isalpha() for c in token) and any(c.isdigit() for c in token)


def _is_distinctive(shingle: str, theory: frozenset[str]) -> bool:
    """True if a shingle carries enough non-stopword, non-theory tokens to be factual content."""
    content = [t for t in shingle.split(" ") if t not in _STOPWORDS and t not in theory]
    return len(content) >= _MIN_CONTENT_TOKENS


def _factual_segments(draft: DraftExtraction | DraftGameSpec) -> list[tuple[str, str]]:
    """Each factual field as ``(location, text)`` — the surface that must trace to supplied facts.

    Excludes ``template_classification`` — that is where the concept library is *meant* to be
    cited.
    """
    segments: list[tuple[str, str]] = []
    for a in draft.game.actors:
        segments.append((f"actor '{a.id}'.name", a.name))
        for k, ev in enumerate(a.evidence):
            segments.append((f"actor '{a.id}' evidence[{k}].source", ev.source))
            segments.append((f"actor '{a.id}' evidence[{k}].note", ev.note))
    for i, asm in enumerate(draft.assumptions):
        segments.append((f"assumptions[{i}].statement", asm.statement))
        segments.append((f"assumptions[{i}].why", asm.why))
    return segments


def find_leaks(
    draft: DraftExtraction | DraftGameSpec,
    allowed_text: str,
    concepts_text: str,
) -> list[Leak]:
    """Return concept-library fragments that leaked into the factual surface, with locations.

    ``allowed_text`` is the supplied situation + sources (the only legitimate provenance for
    facts); ``concepts_text`` is the retrieved template cards + index chunks.
    """
    theory = _theory_vocab()
    allowed_tokens = set(_tokens(allowed_text))
    allowed_shingles = _shingles(_tokens(allowed_text))
    concept_tokens = _tokens(concepts_text)

    concept_only_shingles = {
        s for s in (_shingles(concept_tokens) - allowed_shingles) if _is_distinctive(s, theory)
    }
    concept_only_codes = {t for t in concept_tokens if _is_code(t)} - allowed_tokens

    leaks: list[Leak] = []
    for location, text in _factual_segments(draft):
        toks = _tokens(text)
        for s in sorted(_shingles(toks) & concept_only_shingles):
            leaks.append(Leak(s, location))
        for t in sorted(set(toks) & concept_only_codes):
            leaks.append(Leak(t, location))
    return leaks


def assert_no_leakage(
    draft: DraftExtraction | DraftGameSpec,
    allowed_text: str,
    concepts_text: str,
) -> None:
    """Raise :class:`IndexLeakageError` if any concept-library content reached a factual field."""
    leaks = find_leaks(draft, allowed_text, concepts_text)
    if leaks:
        raise IndexLeakageError(leaks, draft)
