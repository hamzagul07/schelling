"""Tests for the KnowledgeIndex: round-trip + seeded relevance (BUILD_PLAN §7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from schelling.knowledge.chunker import Chunk, chunk_directory
from schelling.knowledge.embed import HashingEmbedder
from schelling.knowledge.index import KnowledgeIndex

TRANSCRIPTS = Path(__file__).parent.parent / "data" / "transcripts"
# The lecture transcripts are gitignored (not redistributable), so they are absent on CI.
_HAS_TRANSCRIPTS = TRANSCRIPTS.exists() and any(TRANSCRIPTS.glob("*.txt"))
_needs_transcripts = pytest.mark.skipif(
    not _HAS_TRANSCRIPTS, reason="lecture transcripts are gitignored; run locally"
)


@pytest.fixture(scope="module")
def chunks() -> list[Chunk]:
    return chunk_directory(TRANSCRIPTS)


def test_index_round_trips_every_chunk(chunks: list[Chunk], tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    index = KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=db)
    assert index.count() == len(chunks)
    index.close()
    # reopen from disk and confirm it still searches (embedder auto-selected from meta)
    reopened = KnowledgeIndex.open(db)
    assert reopened.count() == len(chunks)


@_needs_transcripts
def test_search_returns_chunks_with_refs(chunks: list[Chunk], tmp_path: Path) -> None:
    index = KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=tmp_path / "k.db")
    results = index.search("game theory", k=5)
    assert 1 <= len(results) <= 5
    assert all(r.ref.endswith(".txt)") for r in results)
    # scores are sorted descending (best first)
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)


@_needs_transcripts
def test_seeded_relevance_dating_game(chunks: list[Chunk], tmp_path: Path) -> None:
    # A query whose expected passage is known in advance: the distinctive vocabulary of the
    # opening "Dating Game" lecture (5 men, 5 women, marriage, incels) must surface lecture #1.
    index = KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=tmp_path / "k.db")
    top = index.search("the dating game five men five women marriage incels", k=1)[0]
    assert top.chunk.lecture == "Game Theory #1: The Dating Game"


def test_open_rejects_dimension_mismatch(chunks: list[Chunk], tmp_path: Path) -> None:
    db = tmp_path / "k.db"
    KnowledgeIndex.build(chunks, HashingEmbedder(dim=512), db_path=db).close()
    with pytest.raises(ValueError, match="dim"):
        KnowledgeIndex.open(db, HashingEmbedder(dim=256))


def test_build_is_deterministic(chunks: list[Chunk], tmp_path: Path) -> None:
    a = KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=tmp_path / "a.db")
    b = KnowledgeIndex.build(chunks, HashingEmbedder(), db_path=tmp_path / "b.db")
    qa = [(r.chunk.lecture, round(r.score, 6)) for r in a.search("game theory power", 5)]
    qb = [(r.chunk.lecture, round(r.score, 6)) for r in b.search("game theory power", 5)]
    assert qa == qb


# --------------------------------------------------------------- canon corpus (Session 19)
CANON_DIR = Path(__file__).parent.parent / "data" / "concepts"


def test_canon_cards_are_indexed_and_searchable(tmp_path: Path) -> None:
    from schelling.knowledge.chunker import chunk_concepts_directory

    cards = chunk_concepts_directory(CANON_DIR)
    index = KnowledgeIndex.build(cards, HashingEmbedder(), db_path=tmp_path / "k.db")
    assert index.count() == 29
    hit = index.search("sacred stakes", k=1)[0]
    assert hit.chunk.lecture.startswith("Canon D2") and hit.chunk.source_file == "canon.md"
    index.close()


def test_build_from_corpus_combines_transcripts_and_concepts(tmp_path: Path) -> None:
    # Hermetic: a fake lecture + a fake concept card must both land in the index
    # (CI has no transcripts).
    tdir = tmp_path / "t"
    tdir.mkdir()
    (tdir / "lec.txt").write_text("Game Theory #1: The Dating Game\nFive men, five women.\n")
    cdir = tmp_path / "c"
    cdir.mkdir()
    (cdir / "canon.md").write_text("**A1. Interest asymmetry (Mack 1975).** Weak side prevails.\n")
    index = KnowledgeIndex.build_from_corpus(
        tdir, cdir, embedder=HashingEmbedder(), db_path=tmp_path / "k.db"
    )
    refs = {index.search("anything", k=10)[i].chunk.lecture for i in range(index.count())}
    assert any(r.startswith("Canon A1") for r in refs)  # concept card indexed
    assert any("Dating Game" in r for r in refs)  # transcript lecture indexed
    index.close()
