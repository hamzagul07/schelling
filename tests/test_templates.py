"""Structural validation of the game-template cards (BUILD_PLAN §7)."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any, cast

import yaml

from schelling.knowledge.chunker import lecture_names

TRANSCRIPTS = Path(__file__).parent.parent / "data" / "transcripts"
_REQUIRED_FIELDS = {"name", "conditions", "solution_concept", "transcript_refs", "notes"}

# The eight patterns BUILD_PLAN §7 requires the deck to cover, matched by a distinctive token.
_REQUIRED_CONCEPTS = [
    "Prisoner's Dilemma",
    "Chicken",
    "War of Attrition",
    "Incomplete Information",
    "Signaling",
    "Repeated Games",
    "Commitment",
    "Coalition",
]


def _load_cards() -> list[dict[str, Any]]:
    text = (files("schelling.knowledge") / "templates.yaml").read_text()
    return cast("list[dict[str, Any]]", yaml.safe_load(text)["templates"])


def test_deck_has_10_to_15_cards() -> None:
    assert 10 <= len(_load_cards()) <= 15


def test_every_card_has_all_fields() -> None:
    for card in _load_cards():
        assert set(card) >= _REQUIRED_FIELDS, f"{card.get('name')} missing fields"
        assert card["transcript_refs"], f"{card['name']} has no refs"


def test_required_concepts_are_covered() -> None:
    names = " | ".join(c["name"] for c in _load_cards())
    for concept in _REQUIRED_CONCEPTS:
        assert concept.lower() in names.lower(), f"missing template concept: {concept}"


def test_transcript_refs_are_real_lectures() -> None:
    valid = set(lecture_names(TRANSCRIPTS))
    for card in _load_cards():
        for ref in card["transcript_refs"]:
            assert ref in valid, f"{card['name']} cites unknown lecture: {ref!r}"
