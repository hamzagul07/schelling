"""KnowledgeIndex — chunk store + vector search over sqlite-vec (BUILD_PLAN §7).

``KnowledgeIndex.search(query, k)`` returns chunks with their lecture citation refs. The
sqlite-vec backend lives behind this interface so Phase 2 can swap in pgvector without
touching callers.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sqlite_vec

from schelling.knowledge.chunker import Chunk, chunk_concepts_directory, chunk_directory
from schelling.knowledge.embed import Embedder, HashingEmbedder, make_embedder

DEFAULT_DB_PATH = Path("data/knowledge.db")
DEFAULT_TRANSCRIPTS = Path("data/transcripts")
DEFAULT_CONCEPTS = Path("data/concepts")


@dataclass(frozen=True)
class SearchResult:
    """One search hit: the chunk plus its cosine similarity to the query."""

    chunk: Chunk
    score: float

    @property
    def ref(self) -> str:
        return self.chunk.ref


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


class KnowledgeIndex:
    """A chunk store with vector search, backed by sqlite-vec."""

    def __init__(self, conn: sqlite3.Connection, embedder: Embedder, dim: int) -> None:
        self._conn = conn
        self._embedder = embedder
        self._dim = dim

    # ---------------------------------------------------------------- construction
    @classmethod
    def build(
        cls,
        chunks: list[Chunk],
        embedder: Embedder | None = None,
        db_path: Path = DEFAULT_DB_PATH,
    ) -> KnowledgeIndex:
        """Embed ``chunks`` and build a fresh index at ``db_path`` (overwriting any existing)."""
        emb = embedder or HashingEmbedder()
        if db_path != Path(":memory:") and db_path.exists():
            db_path.unlink()
        if db_path != Path(":memory:"):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _connect(db_path)
        cls._create_schema(conn, emb.dim, emb.name)
        cls._insert(conn, chunks, emb)
        conn.commit()
        return cls(conn, emb, emb.dim)

    @classmethod
    def build_from_transcripts(
        cls,
        transcripts_dir: Path = DEFAULT_TRANSCRIPTS,
        embedder: Embedder | None = None,
        db_path: Path = DEFAULT_DB_PATH,
    ) -> KnowledgeIndex:
        """Chunk every transcript in ``transcripts_dir`` and build the index."""
        return cls.build(chunk_directory(transcripts_dir), embedder, db_path)

    @classmethod
    def build_from_corpus(
        cls,
        transcripts_dir: Path = DEFAULT_TRANSCRIPTS,
        concepts_dir: Path = DEFAULT_CONCEPTS,
        embedder: Embedder | None = None,
        db_path: Path = DEFAULT_DB_PATH,
    ) -> KnowledgeIndex:
        """Build the index from the whole concepts corpus: transcripts + concept cards (Session 19).

        The canon cards in ``concepts_dir`` (``*.md``) join the lecture transcripts as retrievable
        classification concepts. Both remain concepts-library ONLY — never a source of facts
        (rule 6).
        """
        chunks = chunk_directory(transcripts_dir)
        if concepts_dir.exists():
            chunks += chunk_concepts_directory(concepts_dir)
        return cls.build(chunks, embedder, db_path)

    @classmethod
    def open(cls, db_path: Path, embedder: Embedder | None = None) -> KnowledgeIndex:
        """Open an existing index.

        When no embedder is given, the one recorded at build time is reconstructed, so
        ``search`` always matches how the index was built. A supplied embedder must match the
        stored dimension.
        """
        conn = _connect(db_path)
        dim, name = conn.execute("SELECT dim, embedder FROM meta").fetchone()
        emb = embedder or make_embedder(name)
        if emb.dim != dim:
            raise ValueError(f"embedder dim {emb.dim} != index dim {dim}")
        return cls(conn, emb, dim)

    @staticmethod
    def _create_schema(conn: sqlite3.Connection, dim: int, embedder_name: str) -> None:
        conn.execute("CREATE TABLE meta (dim INTEGER, embedder TEXT)")
        conn.execute("INSERT INTO meta (dim, embedder) VALUES (?, ?)", (dim, embedder_name))
        conn.execute(
            "CREATE TABLE chunks ("
            "rowid INTEGER PRIMARY KEY, text TEXT, source_file TEXT, lecture TEXT, "
            "lecture_number INTEGER, chunk_index INTEGER, char_start INTEGER, char_end INTEGER)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE vec_chunks USING "
            f"vec0(embedding float[{dim}] distance_metric=cosine)"
        )

    @staticmethod
    def _insert(conn: sqlite3.Connection, chunks: list[Chunk], embedder: Embedder) -> None:
        if not chunks:
            return
        vectors = embedder.embed([c.text for c in chunks])
        for rowid, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True), start=1):
            conn.execute(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rowid,
                    chunk.text,
                    chunk.source_file,
                    chunk.lecture,
                    chunk.lecture_number,
                    chunk.chunk_index,
                    chunk.char_start,
                    chunk.char_end,
                ),
            )
            conn.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (rowid, np.asarray(vec, dtype=np.float32).tobytes()),
            )

    # ---------------------------------------------------------------- query
    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return the top-``k`` chunks most similar to ``query`` (cosine), best first."""
        vec = self._embedder.embed([query])[0]
        rows = self._conn.execute(
            "SELECT rowid, distance FROM vec_chunks "
            "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (np.asarray(vec, dtype=np.float32).tobytes(), k),
        ).fetchall()
        results: list[SearchResult] = []
        for rowid, distance in rows:
            chunk = self._load_chunk(rowid)
            results.append(SearchResult(chunk=chunk, score=1.0 - float(distance)))
        return results

    def _load_chunk(self, rowid: int) -> Chunk:
        row = self._conn.execute(
            "SELECT text, source_file, lecture, lecture_number, chunk_index, char_start, char_end "
            "FROM chunks WHERE rowid = ?",
            (rowid,),
        ).fetchone()
        return Chunk(
            text=row[0],
            source_file=row[1],
            lecture=row[2],
            lecture_number=row[3],
            chunk_index=row[4],
            char_start=row[5],
            char_end=row[6],
        )

    def count(self) -> int:
        (n,) = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return int(n)

    def close(self) -> None:
        self._conn.close()
