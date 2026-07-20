"""Tests for transcript chunking (BUILD_PLAN §7)."""

from __future__ import annotations

from pathlib import Path

from schelling.knowledge.chunker import (
    chunk_directory,
    chunk_text,
    lecture_names,
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


def test_chunk_offsets_map_back_to_source_bytes() -> None:
    for path in sorted(TRANSCRIPTS.glob("*.txt")):
        source = path.read_text(encoding="utf-8-sig")
        for chunk in chunk_text(source, path.name):
            assert source[chunk.char_start : chunk.char_end] == chunk.text


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
