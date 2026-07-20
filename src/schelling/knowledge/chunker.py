"""Split transcript files into per-lecture chunks (BUILD_PLAN §7).

The source material is detailed lecture *summaries* (not verbatim transcripts) from the
"Predictive History" game-theory series. Each file holds ~10 lectures, each introduced by a
standalone heading line ``Game Theory #N: <Title>``. We split on those headings, then window
each lecture into ~800-token chunks with 15% overlap, preserving the source file, the lecture
name (used as the citation ref), and character offsets into the source file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# A lecture heading is a line that *starts* with "Game Theory #N:" — this distinguishes true
# headings from body sentences that merely quote a title (e.g. 'Based on the transcript "...").
_HEADING = re.compile(r"^Game Theory #(\d+):[ \t]*(.+?)[ \t]*$", re.MULTILINE)
_WORD = re.compile(r"\S+")

# ~800 tokens with 15% overlap. We estimate tokens as words * 1.3 (typical English ratio),
# so a chunk targets ~615 words and overlaps ~92 (D4.x).
TOKENS_PER_WORD = 1.3
TARGET_TOKENS = 800
OVERLAP_FRACTION = 0.15
_WORDS_PER_CHUNK = round(TARGET_TOKENS / TOKENS_PER_WORD)
_OVERLAP_WORDS = round(TARGET_TOKENS * OVERLAP_FRACTION / TOKENS_PER_WORD)


@dataclass(frozen=True)
class Lecture:
    """One lecture section within a source file."""

    number: int
    title: str
    source_file: str
    char_start: int  # offset of the heading in the source file
    char_end: int  # offset of the next heading (or EOF)
    text: str  # the lecture body, heading included

    @property
    def name(self) -> str:
        """Canonical lecture name, e.g. ``Game Theory #1: The Dating Game``."""
        return f"Game Theory #{self.number}: {self.title}"


@dataclass(frozen=True)
class Chunk:
    """One embeddable chunk, carrying its lecture citation ref and source offsets."""

    text: str
    source_file: str
    lecture: str  # the lecture name (citation ref)
    lecture_number: int
    chunk_index: int  # index of this chunk within its lecture
    char_start: int  # offset into the source file
    char_end: int

    @property
    def ref(self) -> str:
        """Human-readable citation: lecture name plus source file (BUILD_PLAN §7)."""
        return f"{self.lecture} ({self.source_file})"


def split_lectures(text: str, source_file: str) -> list[Lecture]:
    """Split a file's text into lectures on ``Game Theory #N:`` headings, in order."""
    matches = list(_HEADING.finditer(text))
    lectures: list[Lecture] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        lectures.append(
            Lecture(
                number=int(match.group(1)),
                title=match.group(2).strip(),
                source_file=source_file,
                char_start=start,
                char_end=end,
                text=text[start:end],
            )
        )
    return lectures


def chunk_lecture(lecture: Lecture) -> list[Chunk]:
    """Window one lecture into ~800-token chunks with 15% overlap, preserving file offsets."""
    words = list(_WORD.finditer(lecture.text))
    if not words:
        return []
    step = max(1, _WORDS_PER_CHUNK - _OVERLAP_WORDS)
    chunks: list[Chunk] = []
    start_word = 0
    chunk_index = 0
    while start_word < len(words):
        window = words[start_word : start_word + _WORDS_PER_CHUNK]
        local_start = window[0].start()
        local_end = window[-1].end()
        chunks.append(
            Chunk(
                text=lecture.text[local_start:local_end],
                source_file=lecture.source_file,
                lecture=lecture.name,
                lecture_number=lecture.number,
                chunk_index=chunk_index,
                char_start=lecture.char_start + local_start,
                char_end=lecture.char_start + local_end,
            )
        )
        chunk_index += 1
        if start_word + _WORDS_PER_CHUNK >= len(words):
            break
        start_word += step
    return chunks


def chunk_text(text: str, source_file: str) -> list[Chunk]:
    """Split file text into lectures and window each into chunks."""
    chunks: list[Chunk] = []
    for lecture in split_lectures(text, source_file):
        chunks.extend(chunk_lecture(lecture))
    return chunks


def chunk_file(path: Path) -> list[Chunk]:
    """Chunk one transcript file (UTF-8, BOM-tolerant)."""
    return chunk_text(path.read_text(encoding="utf-8-sig"), path.name)


def chunk_directory(directory: Path) -> list[Chunk]:
    """Chunk every ``*.txt`` transcript in ``directory`` (sorted for determinism)."""
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.txt")):
        chunks.extend(chunk_file(path))
    return chunks


def lecture_names(directory: Path) -> list[str]:
    """List every detected lecture name across the directory (for heading-pattern review)."""
    names: list[str] = []
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        names.extend(lec.name for lec in split_lectures(text, path.name))
    return names
