"""Embedding backends behind a small protocol (BUILD_PLAN §7).

The production embedder is bge-m3 (local, downloads on first use). Tests and offline runs use
a deterministic, dependency-free hashing embedder so nothing needs a 2GB model or network. All
embedders return L2-normalized ``float32`` rows, so cosine similarity is a dot product.
"""

from __future__ import annotations

import re
from itertools import pairwise
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

FloatMatrix = npt.NDArray[np.float32]

_TOKEN = re.compile(r"[a-z0-9]+")


@runtime_checkable
class Embedder(Protocol):
    """Maps texts to L2-normalized embedding rows."""

    @property
    def name(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> FloatMatrix: ...


def make_embedder(name: str) -> Embedder:
    """Construct an embedder by name (``"hashing"`` or ``"bge-m3"``)."""
    if name == "hashing":
        return HashingEmbedder()
    if name == "bge-m3":
        return BgeM3Embedder()
    raise ValueError(f"unknown embedder {name!r} (expected 'hashing' or 'bge-m3')")


def _l2_normalize(matrix: FloatMatrix) -> FloatMatrix:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return (matrix / norms).astype(np.float32)


class HashingEmbedder:
    """Deterministic bag-of-token-hashes embedder — lexical, not semantic (tests / offline).

    Each lowercased word token (plus adjacent bigrams for a little phrase sensitivity) is
    hashed into a fixed-width vector with TF weighting, then L2-normalized. Cosine similarity
    then tracks shared vocabulary: a query shares direction with passages that use its words.
    Fully deterministic (stable hashing), so relevance tests are reproducible.
    """

    def __init__(self, dim: int = 512) -> None:
        self._dim = dim

    @property
    def name(self) -> str:
        return "hashing"

    @property
    def dim(self) -> int:
        return self._dim

    def _tokens(self, text: str) -> list[str]:
        words = _TOKEN.findall(text.lower())
        bigrams = [f"{a}_{b}" for a, b in pairwise(words)]
        return words + bigrams

    def embed(self, texts: list[str]) -> FloatMatrix:
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in self._tokens(text):
                # Stable, process-independent hash (hashlib), folded into the vector width.
                bucket = int.from_bytes(_stable_hash(token), "big") % self._dim
                out[row, bucket] += 1.0
        return _l2_normalize(out)


def _stable_hash(token: str) -> bytes:
    import hashlib

    return hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()


class BgeM3Embedder:
    """Local bge-m3 embeddings via ``sentence-transformers`` (BUILD_PLAN §7).

    Lazy-imports ``sentence_transformers`` and lazy-loads the model so importing this module
    never pulls torch. The model downloads on first use (needs network); install the extra with
    ``uv sync --extra knowledge``.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model_name = model_name
        self._model: object | None = None
        self._dim = 1024  # bge-m3 embedding dimension

    @property
    def name(self) -> str:
        return "bge-m3"

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure_model(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise ImportError(
                    "bge-m3 needs the 'knowledge' extra: uv sync --extra knowledge"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> FloatMatrix:
        model = self._ensure_model()
        vectors = model.encode(  # type: ignore[attr-defined]
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return np.asarray(vectors, dtype=np.float32)
