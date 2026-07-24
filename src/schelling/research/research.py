"""The iterative research loop (D38.1).

``run_research`` gathers evidence in rounds — a broad survey, then targeted searches for the
coordinates the game still lacks, then a contradiction-resolution pass — and stops when a round adds
essentially no new claims, when no gaps remain, or when the budget is spent, rather than after a
fixed number of searches. It is resumable (pass the prior corpus) and caches sources by URL. The
LLM only *structures* evidence (extracts claims, tags confidence, names gaps); no probability is
produced here (rule 1) and the concept index is never consulted (the firewall is untouched).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import cast

from schelling.formalizer.client import (
    AnthropicClient,
    LLMClient,
    Message,
    WebSource,
    cost_usd,
    search_cost_usd,
)
from schelling.research.corpus import merge_round, situation_hash
from schelling.research.schemas import Claim, Confidence, ResearchCorpus, ResearchSource, RoundLog

_MAX_TOKENS = 8000
_VALID_CONFIDENCE = {"established", "reported", "contested", "inferred"}
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _system_prompt() -> str:
    return (
        "You are the evidence-gathering stage of a forecasting engine. You DO NOT forecast and you "
        "produce NO probabilities — you gather and structure evidence for a bargaining game. For "
        "the given question, search the web and extract atomic CLAIMS about the actors and their "
        "positions, saliences, and capabilities.\n"
        "Tag every claim with a confidence level, using exactly one of:\n"
        "  established — multiple independent primary sources agree;\n"
        "  reported    — a single credible source;\n"
        "  contested   — sources disagree (record every side, with each side's reading);\n"
        "  inferred    — no source; your own reasoning, stated as such.\n"
        "Where a claim pins a game coordinate, set `addresses` to `<actor_id>.<param>` (param in "
        "{position, salience, capability}) and put the numeric reading(s) on the 0-100 continuum "
        "in `readings`. If sources disagree on a coordinate, emit it as `contested` with all the "
        "readings — never resolve a disagreement to one side.\n"
        "Then name the GAPS that remain — coordinates still unknown or claims still unsupported.\n"
        "Reply with ONE JSON object and nothing else:\n"
        '{"claims": [{"text": "...", "confidence": "reported", "addresses": "actor_id.position", '
        '"readings": [66], "source_urls": ["https://..."]}], "gaps": ["what is still unknown"]}'
    )


def _round_prompt(situation_text: str, corpus: ResearchCorpus, kind: str) -> str:
    parts = [f"QUESTION / SITUATION:\n{situation_text.strip()}"]
    if kind == "survey":
        parts.append(
            "\nROUND: broad survey. Establish who the actors are and gather first evidence on each "
            "one's position, salience, and capability. Then name the gaps that remain."
        )
    else:
        conf = corpus.coordinate_confidence()
        known = "; ".join(f"{c}={conf[c]}" for c in sorted(conf)) or "(none yet)"
        gaps = "; ".join(corpus.gaps_remaining) or "(none listed)"
        parts.append(f"\nCOORDINATES ESTABLISHED SO FAR: {known}")
        parts.append(f"GAPS TO CLOSE: {gaps}")
        if kind == "contradiction":
            contested = [c for c, cf in conf.items() if cf == "contested"]
            parts.append(
                "\nROUND: contradiction resolution. For each CONTESTED coordinate below, search "
                "for more evidence and record EVERY side's reading — do not resolve to one. "
                f"Contested: {'; '.join(contested) or '(none)'}."
            )
        else:
            parts.append(
                "\nROUND: targeted. Search specifically to close the gaps above and to strengthen "
                "the weakest coordinates. Only return NEW claims; if a source disagrees with an "
                "established coordinate, emit it as contested with both readings."
            )
    parts.append(
        "\nReturn the JSON object of claims and remaining gaps. Return an empty `gaps` list only "
        "when the game's coordinates are all supported."
    )
    return "\n".join(parts)


def _extract_json(text: str) -> dict[str, object] | None:
    """The top-level JSON object in a model reply, tolerating fences and a preamble."""
    for candidate in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        chunks = [candidate]
        match = _OBJECT.search(candidate)
        if match is not None:
            chunks.append(match.group(0))
        for chunk in chunks:
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def _parse_round(
    text: str, sources: tuple[WebSource, ...], retrieved_at: str
) -> tuple[list[ResearchSource], list[Claim], list[str]]:
    obj = _extract_json(text) or {}
    src = [
        ResearchSource(url=s.url, title=s.title, retrieved_at=retrieved_at, snippet=s.snippet)
        for s in sources
    ]
    raw_claims = obj.get("claims")
    claims: list[Claim] = []
    for raw in raw_claims if isinstance(raw_claims, list) else []:
        if not isinstance(raw, dict) or not raw.get("text"):
            continue
        conf = str(raw.get("confidence", "inferred"))
        confidence = cast("Confidence", conf if conf in _VALID_CONFIDENCE else "inferred")
        rlist = raw.get("readings")
        readings = (
            [float(r) for r in rlist if isinstance(r, int | float)]
            if isinstance(rlist, list)
            else []
        )
        ulist = raw.get("source_urls")
        urls = [str(u) for u in ulist if isinstance(u, str)] if isinstance(ulist, list) else []
        if confidence != "contested" and not urls:
            confidence = "inferred"  # no source -> inferred
        claims.append(
            Claim(
                text=str(raw["text"]).strip(),
                confidence=confidence,
                source_urls=urls,
                addresses=str(raw.get("addresses", "") or ""),
                readings=readings,
            )
        )
    raw_gaps = obj.get("gaps")
    gaps = [str(g) for g in raw_gaps if isinstance(g, str)] if isinstance(raw_gaps, list) else []
    return src, claims, gaps


def run_research(
    situation_text: str,
    *,
    client: LLMClient | None = None,
    frozen_at: str,
    budget: float | None = None,
    prior: ResearchCorpus | None = None,
    max_searches_per_round: int = 5,
    max_rounds: int = 8,
    on_round: Callable[[RoundLog], None] | None = None,
) -> ResearchCorpus:
    """Gather evidence in rounds until marginal information approaches zero (D38.1).

    Stops when a round after the first adds no new claim (``marginal``), when no gaps remain
    (``no_gaps``), when the running spend reaches ``budget`` (``budget``), or at ``max_rounds``.
    Resumes from ``prior`` if given. Reports each round through ``on_round``.
    """
    llm = client or AnthropicClient()
    corpus = prior or ResearchCorpus(
        situation_hash=situation_hash(situation_text), frozen_at=frozen_at
    )
    cumulative = corpus.total_cost_usd
    round_no = len(corpus.rounds)
    system = _system_prompt()

    def do_round(kind: str) -> int:
        nonlocal corpus, cumulative, round_no
        round_no += 1
        result = llm.complete(
            system,
            [Message("user", _round_prompt(situation_text, corpus, kind))],
            _MAX_TOKENS,
            search=True,
            max_searches=max_searches_per_round,
        )
        cost = cost_usd(llm.model, result.input_tokens, result.output_tokens) + search_cost_usd(
            result.searches_used
        )
        cumulative += cost
        src, claims, gaps = _parse_round(result.text, result.sources, frozen_at)
        corpus, n_new_claims, n_new_sources = merge_round(corpus, src, claims)
        corpus.gaps_remaining = gaps
        log = RoundLog(
            round=round_no,
            kind=kind,
            new_claims=n_new_claims,
            new_sources=n_new_sources,
            gaps_remaining=gaps,
            cost_usd=round(cost, 6),
            cumulative_cost_usd=round(cumulative, 6),
        )
        corpus.rounds = [*corpus.rounds, log]
        if on_round is not None:
            on_round(log)
        return n_new_claims

    while True:
        if budget is not None and cumulative >= budget:
            corpus.stopped_reason = "budget"
            break
        kind = "survey" if round_no == 0 else "targeted"
        n_new = do_round(kind)
        if not corpus.gaps_remaining:
            corpus.stopped_reason = "no_gaps"
            break
        if kind != "survey" and n_new == 0:
            corpus.stopped_reason = "marginal"
            break
        if round_no >= max_rounds:
            corpus.stopped_reason = "max_rounds"
            break

    # one contradiction-resolution pass if disagreements remain and budget allows
    contested = [c for c, cf in corpus.coordinate_confidence().items() if cf == "contested"]
    if contested and (budget is None or cumulative < budget):
        do_round("contradiction")

    corpus.total_cost_usd = round(cumulative, 6)
    return corpus
