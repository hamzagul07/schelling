"""Read, write, and grow the research corpus on disk (D38.1).

A corpus is a directory: ``corpus.json`` (the :class:`ResearchCorpus`) plus ``situation.txt`` (the
question it was built from, so ``formalize --corpus`` needs nothing else). :func:`merge_round` is
the cache: sources are unique by URL — a URL already present keeps its original retrieval date and
is never re-added — and claims are unique by key, so re-runs and ``--resume`` never duplicate work.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from schelling.research.schemas import Claim, ResearchCorpus, ResearchSource

CORPUS_FILE = "corpus.json"
SITUATION_FILE = "situation.txt"


def situation_hash(situation_text: str) -> str:
    """A stable content hash of the situation, so a corpus is tied to the question it researched."""
    return hashlib.sha256(situation_text.encode()).hexdigest()


def write_corpus(directory: Path, corpus: ResearchCorpus, situation_text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / CORPUS_FILE).write_text(corpus.model_dump_json(indent=2) + "\n")
    (directory / SITUATION_FILE).write_text(situation_text)


def load_corpus(directory: Path) -> tuple[ResearchCorpus, str]:
    """Load ``(corpus, situation_text)`` from a corpus directory (for --resume and --corpus)."""
    corpus = ResearchCorpus.model_validate_json((directory / CORPUS_FILE).read_text())
    situation_text = (directory / SITUATION_FILE).read_text()
    return corpus, situation_text


def merge_round(
    corpus: ResearchCorpus, new_sources: list[ResearchSource], new_claims: list[Claim]
) -> tuple[ResearchCorpus, int, int]:
    """Fold a round's sources and claims into the corpus, deduplicated (the cache, D38.1).

    A source whose URL is already cached is dropped (its original ``retrieved_at`` is kept); a claim
    whose key already exists is dropped. Returns the grown corpus and the counts of genuinely new
    sources and claims — the latter drives the stop-on-marginal-information test."""
    seen_urls = corpus.source_urls()
    added_sources = [
        s for s in new_sources if s.url not in seen_urls and not _dup(s.url, seen_urls)
    ]
    # add-order dedup within the round too
    kept_sources: list[ResearchSource] = []
    round_urls: set[str] = set()
    for s in added_sources:
        if s.url in round_urls:
            continue
        round_urls.add(s.url)
        kept_sources.append(s)

    seen_keys = corpus.claim_keys()
    kept_claims: list[Claim] = []
    round_keys: set[str] = set()
    for c in new_claims:
        k = c.key()
        if k in seen_keys or k in round_keys:
            continue
        round_keys.add(k)
        kept_claims.append(c)

    grown = corpus.model_copy(
        update={
            "sources": [*corpus.sources, *kept_sources],
            "claims": [*corpus.claims, *kept_claims],
        }
    )
    return grown, len(kept_claims), len(kept_sources)


def _dup(url: str, seen: set[str]) -> bool:
    return url in seen


def corpus_to_sources(corpus: ResearchCorpus) -> dict[str, str]:
    """Build the offline ``sources`` map (name -> text) the formalizer consumes (D38.3).

    Every source and every claim lands in the returned text, so the whole corpus is inside the
    formalizer's allowed evidence (the firewall is unchanged) and each claim can be cited.
    Confidence tags travel with the claims so the reviewer sees why a range is wide or narrow."""
    out: dict[str, str] = {}
    for s in corpus.sources:
        out[f"source::{s.url}"] = f"{s.title} ({s.url}, retrieved {s.retrieved_at})\n{s.snippet}"
    if corpus.claims:
        lines = []
        for c in corpus.claims:
            reading = (
                f" [readings: {', '.join(f'{r:g}' for r in c.readings)}]" if c.readings else ""
            )
            coord = f" ({c.addresses})" if c.addresses else ""
            lines.append(f"[{c.confidence}]{coord} {c.text}{reading}")
        out["corpus-claims"] = "\n".join(lines)
    return out
