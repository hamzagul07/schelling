"""Tests for transcript chunking (BUILD_PLAN §7)."""

from __future__ import annotations

from pathlib import Path

from schelling.knowledge.chunker import (
    chunk_directory,
    chunk_text,
    lecture_names,
    normalize_document,
    split_lectures,
)

TRANSCRIPTS = Path(__file__).parent.parent / "data" / "transcripts"

SAMPLE = (
    "Game Theory #1: The Alpha\n"
    "Body of the first lecture about war of attrition and bluffing.\n"
    "Game Theory #2: The Beta\n"
    'Based on the transcript "Game Theory #2: The Beta", a summary about signaling.\n'
)


def test_split_lectures_detects_headings_not_body_mentions() -> None:
    lectures = split_lectures(SAMPLE, "sample.txt")
    assert [lec.number for lec in lectures] == [1, 2]
    assert lectures[0].name == "Game Theory #1: The Alpha"
    # the quoted title inside lecture 2's body must NOT create a third lecture
    assert len(lectures) == 2


def test_lecture_char_ranges_partition_the_text() -> None:
    lectures = split_lectures(SAMPLE, "sample.txt")
    assert lectures[0].char_start == 0
    assert lectures[0].char_end == lectures[1].char_start
    assert lectures[1].char_end == len(SAMPLE)


def test_chunk_ref_cites_lecture_and_file() -> None:
    chunk = chunk_text(SAMPLE, "sample.txt")[0]
    assert chunk.ref == "Game Theory #1: The Alpha (sample.txt)"


def test_real_transcripts_yield_29_lectures() -> None:
    names = lecture_names(TRANSCRIPTS)
    assert len(names) == 29
    assert names[0] == "Game Theory #1: The Dating Game"
    assert names[-1] == "Game Theory #29: Final Examination"


def test_chunk_offsets_map_back_to_normalized_source() -> None:
    # Offsets are relative to the normalized text (boilerplate stripped, D5.1).
    for path in sorted(TRANSCRIPTS.glob("*.txt")):
        normalized = normalize_document(path.read_text(encoding="utf-8-sig"))
        for chunk in chunk_text(normalized, path.name, normalize=False):
            assert normalized[chunk.char_start : chunk.char_end] == chunk.text


def test_normalizer_strips_ai_summary_boilerplate() -> None:
    raw = (
        "Game Theory #1: The Alpha\n"
        "Here is a comprehensive and detailed summary of the video.\n"
        "Based on the transcript, the professor argues X.\n"
        "The actual game-theory content about war of attrition.\n"
    )
    out = normalize_document(raw)
    assert "Here is a comprehensive" not in out
    assert "Based on the transcript" not in out
    assert "Game Theory #1: The Alpha" in out  # heading preserved
    assert "war of attrition" in out  # substantive content preserved


def test_chunks_carry_lecture_provenance() -> None:
    chunks = chunk_directory(TRANSCRIPTS)
    assert len(chunks) >= 29  # at least one chunk per lecture
    assert all(c.lecture.startswith("Game Theory #") for c in chunks)
    assert {c.source_file for c in chunks} == {p.name for p in TRANSCRIPTS.glob("*.txt")}


def test_long_lecture_is_split_with_overlap() -> None:
    # A lecture longer than one window produces overlapping chunks (shared text at the seam).
    body = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(f"Game Theory #1: Long\n{body}", "long.txt")
    assert len(chunks) >= 2
    # consecutive chunks overlap in the source (next starts before current ends)
    assert chunks[1].char_start < chunks[0].char_end


# --------------------------------------------------------------- concept-card chunking (Session 19)
CANON = Path(__file__).parent.parent / "data" / "concepts" / "canon.md"


def test_chunk_concept_cards_splits_every_canon_card() -> None:
    from schelling.knowledge.chunker import chunk_concept_cards

    cards = chunk_concept_cards(CANON.read_text(), "canon.md")
    assert len(cards) == 29  # families A1-A7, B1-B5, C1-C7, D1-D7, E1-E3
    refs = {c.lecture for c in cards}
    assert "Canon A3: Loss-domain risk seeking" in refs
    assert "Canon D2: Indivisibility and sacred stakes" in refs
    a3 = next(c for c in cards if c.lecture.startswith("Canon A3"))
    assert "loss-domain risk seeking" in a3.text.lower() and a3.source_file == "canon.md"


def test_chunk_concept_cards_handles_multiline_citation_header() -> None:
    # A5's citation list wraps across a line ("Trachtenberg\n2012)") — DOTALL keeps the card whole.
    from schelling.knowledge.chunker import chunk_concept_cards

    cards = chunk_concept_cards(CANON.read_text(), "canon.md")
    assert any(c.lecture == "Canon A5: Audience costs" for c in cards)


def test_chunk_concepts_directory_reads_md(tmp_path: Path) -> None:
    from schelling.knowledge.chunker import chunk_concepts_directory

    (tmp_path / "x.md").write_text("**A1. Foo (Bar 2020).** Body text here.\n")
    chunks = chunk_concepts_directory(tmp_path)
    assert len(chunks) == 1 and chunks[0].lecture == "Canon A1: Foo"
