"""``formalize(situation_text, sources) -> DraftGameSpec`` (Phase 1).

The LLM structures a described situation into a solver-ready game with ranged inputs, sourced
evidence, a template classification, and an explicit assumptions list. Output is strict JSON
validated by the pydantic schemas with a bounded retry loop; a concepts-library firewall then
verifies nothing retrieved leaked into a factual field. Never auto-solves.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

import yaml
from pydantic import ValidationError

from schelling.formalizer.client import (
    DEFAULT_MODEL,
    AnthropicClient,
    LLMClient,
    Message,
    cost_usd,
)
from schelling.formalizer.firewall import assert_no_leakage
from schelling.formalizer.prompt import build_system_prompt, build_user_prompt
from schelling.formalizer.schemas import DraftExtraction, DraftGameSpec, DraftMetadata
from schelling.knowledge.index import KnowledgeIndex


class FormalizeError(RuntimeError):
    """The model did not return valid JSON matching the schema within the retry budget."""


def _load_template_cards() -> list[dict[str, Any]]:
    text = (files("schelling.knowledge") / "templates.yaml").read_text()
    return cast("list[dict[str, Any]]", yaml.safe_load(text)["templates"])


def _card_lines(cards: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for c in cards:
        conditions = " ".join(str(c.get("conditions", "")).split())
        concept = " ".join(str(c.get("solution_concept", "")).split())
        lines.append(f"{c['name']} — when: {conditions} | solution: {concept}")
    return lines


def _chunk_lines(index: KnowledgeIndex | None, query: str, k: int) -> tuple[list[str], str]:
    """Return (prompt lines, concepts-text) for the top-k retrieved chunks."""
    if index is None:
        return [], ""
    results = index.search(query, k=k)
    lines = []
    concept_parts = []
    for r in results:
        snippet = " ".join(r.chunk.text.split())[:300]
        lines.append(f"{r.chunk.ref}: {snippet}")
        concept_parts.append(r.chunk.text)
    return lines, "\n".join(concept_parts)


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a completion (tolerates prose or ``` fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in the completion")
    return text[start : end + 1]


def formalize(
    situation_text: str,
    sources: dict[str, str] | None = None,
    *,
    client: LLMClient | None = None,
    index: KnowledgeIndex | None = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
    max_tokens: int = 16_000,
    top_k_chunks: int = 6,
    created_at: str | None = None,
) -> DraftGameSpec:
    """Formalize ``situation_text`` (+ optional ``sources``) into a reviewable draft game.

    ``client`` defaults to a live :class:`AnthropicClient`; tests inject a record/replay client.
    ``index`` (optional) supplies concept-library grounding for the template choice — never
    facts. On validation failure the model is re-prompted with the error, up to ``max_retries``
    extra attempts. A firewall then rejects any concept-library leakage into factual fields.
    """
    sources = sources or {}
    llm = client or AnthropicClient(model=model)

    cards = _load_template_cards()
    card_lines = _card_lines(cards)
    chunk_lines, chunk_concepts = _chunk_lines(index, situation_text, top_k_chunks)

    system = build_system_prompt()
    user = build_user_prompt(situation_text, sources, card_lines, chunk_lines)
    messages: list[Message] = [Message("user", user)]

    total_in = 0
    total_out = 0
    extraction: DraftExtraction | None = None
    last_error = ""
    attempts = max_retries + 1
    for attempt in range(attempts):
        result = llm.complete(system, messages, max_tokens)
        total_in += result.input_tokens
        total_out += result.output_tokens
        try:
            data = json.loads(_extract_json(result.text))
            extraction = DraftExtraction.model_validate(data)
            retries = attempt
            break
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)
            if attempt == attempts - 1:
                raise FormalizeError(
                    f"no valid draft after {attempts} attempts; last error: {last_error}"
                ) from exc
            messages.append(Message("assistant", result.text))
            messages.append(
                Message(
                    "user",
                    "That did not validate against the schema:\n"
                    f"{last_error}\n"
                    "Return ONLY the corrected JSON object.",
                )
            )
    assert extraction is not None  # loop either breaks with a value or raises

    # Firewall: no concept-library content may reach a factual field (CLAUDE.md rule 6).
    allowed_text = "\n".join([situation_text, *sources.values()])
    concepts_text = "\n".join([*card_lines, chunk_concepts])
    assert_no_leakage(extraction, allowed_text, concepts_text)

    metadata = DraftMetadata(
        model=llm.model,
        input_tokens=total_in,
        output_tokens=total_out,
        cost_usd=round(cost_usd(llm.model, total_in, total_out), 6),
        retries=retries,
        created_at=created_at,
    )
    return DraftGameSpec(
        game=extraction.game,
        assumptions=extraction.assumptions,
        template_classification=extraction.template_classification,
        metadata=metadata,
    )
