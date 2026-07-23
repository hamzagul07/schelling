"""Find prior comparable decisions — the outside view (Session 29, D29.1).

One LLM call (optionally web-searching) that identifies prior decisions of the same body / dyad /
institution / decision type, and for each proposes a placement on the current question's 0-100
continuum with one line of reasoning. Everything is a PROPOSAL — nothing is auto-accepted; a human
ratifies before a precedent becomes evidence or enters the reference-class panel (D29.2).
"""

from __future__ import annotations

import json
import re
from typing import Any

from schelling.formalizer.client import LLMClient, Message, cost_usd, search_cost_usd
from schelling.precedents.schemas import PrecedentSet
from schelling.schemas.forecast import Precedent
from schelling.schemas.question import GameSpec

# Extraction is on the client's concatenated text blocks (LLMResult.text) — the one block-parsing
# implementation lives in formalizer.client._parse_response; precedents does not duplicate it (D30).
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
# A search + adaptive-thinking response spends heavily on thinking and tool use before the JSON;
# 4000 truncated it mid-preamble (D30). Give the array room, and demand JSON-only in the prompt.
_MAX_TOKENS = 8000
_STRICTER = (
    "You did not return a usable JSON array. Reply now with ONLY the JSON array of precedents — "
    "start with [ and end with ], no preamble, no notes, no code fences, no commentary."
)


class PrecedentSearchError(RuntimeError):
    """The model returned no parseable precedent list."""


def _system_prompt() -> str:
    return (
        "You identify PRIOR COMPARABLE DECISIONS for a forecasting question — the outside view. "
        "Find real prior decisions of the SAME body, the SAME dyad, the SAME institution, or the "
        "SAME decision type. For each, return: what happened, its date, a source citation, a "
        "PROPOSED placement on the current 0-100 continuum, one line of reasoning, and whether it "
        "is ex-ante codable (codable from information available before that decision's own outcome "
        "was known) or hindsight-coded. Cite a real source for every precedent; never invent one. "
        "These are PROPOSALS for a human to ratify — do not overstate confidence.\n"
        "CRITICAL: reply with ONLY the JSON array and nothing else — no preamble, no notes, no "
        "code fences, no commentary. Start your reply with [ and end with ]. Each element:\n"
        '{"id": "...", "what_happened": "...", "date": "YYYY-MM", "source": "...", '
        '"proposed_placement": <0-100>, "reasoning": "one line", "ex_ante_codable": true|false}'
    )


def _user_prompt(game: GameSpec, sources_text: str) -> str:
    c = game.continuum
    parts = [
        f"QUESTION {game.question_id}",
        f"CONTINUUM (0-100): {c.label}. 0 = {c.anchor_0}. 100 = {c.anchor_100}.",
        f"HORIZON: {game.horizon}.",
    ]
    if game.notes:
        parts.append(f"NOTES: {game.notes}")
    parts.append("ACTORS: " + "; ".join(a.name for a in game.actors))
    if sources_text.strip():
        parts.append("\nFETCHED SOURCES:\n" + sources_text.strip())
    parts.append("\nReturn the JSON array of prior comparable decisions.")
    return "\n".join(parts)


def _extract_precedent_list(text: str) -> list[dict[str, Any]]:
    """Pull a precedent list out of the model's text, tolerating fences, a preamble before/after
    the JSON, a ``{"precedents": [...]}`` wrapper, and a single object instead of an array (D30)."""
    # Try fenced blocks first (their content is the cleanest), then the whole text.
    for candidate in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        arr = _ARRAY.search(candidate)
        if arr is not None:
            try:
                obj = json.loads(arr.group(0))
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, list):
                return [e for e in obj if isinstance(e, dict)]
        found = _OBJECT.search(candidate)
        if found is not None:
            try:
                obj = json.loads(found.group(0))
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                inner = obj.get("precedents")
                if isinstance(inner, list):
                    return [e for e in inner if isinstance(e, dict)]
                return [obj]  # a single object -> a one-element list
    raise PrecedentSearchError("no JSON array or object in the model response")


def parse_precedents(text: str) -> list[Precedent]:
    """Parse a model response into unratified :class:`Precedent` proposals (raises if none)."""
    raw = _extract_precedent_list(text)
    out: list[Precedent] = []
    for i, obj in enumerate(raw):
        try:
            out.append(
                Precedent(
                    id=str(obj.get("id") or f"prec-{i + 1}"),
                    what_happened=str(obj["what_happened"]),
                    date=str(obj["date"]),
                    source=str(obj["source"]),
                    proposed_placement=float(obj["proposed_placement"]),
                    reasoning=str(obj["reasoning"]),
                    ex_ante_codable=bool(obj["ex_ante_codable"]),
                    ratified=False,  # never auto-accepted (D29.2)
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip a malformed entry rather than fail the whole batch
    return out


def find_precedents(
    client: LLMClient,
    game: GameSpec,
    *,
    sources_text: str = "",
    search: bool = False,
    max_searches: int = 5,
    created_at: str | None = None,
    max_retries: int = 1,
) -> PrecedentSet:
    """LLM call(s) producing a :class:`PrecedentSet` of unratified proposals (D29.1).

    Retries once with a stricter JSON-only instruction if the first reply is unparseable (e.g. the
    model spent its budget on search + preamble and was truncated before the array, D30). On final
    failure the error carries the first 300 characters of what was actually returned.
    """
    system = _system_prompt()
    messages = [Message("user", _user_prompt(game, sources_text))]
    last_text = ""
    in_tok = out_tok = searches = 0
    for _attempt in range(max_retries + 1):
        result = client.complete(
            system, messages, _MAX_TOKENS, search=search, max_searches=max_searches
        )
        last_text = result.text
        in_tok += result.input_tokens
        out_tok += result.output_tokens
        searches += result.searches_used
        try:
            precedents = parse_precedents(result.text)
        except PrecedentSearchError:
            precedents = []
        if precedents:
            cost = cost_usd(client.model, in_tok, out_tok) + search_cost_usd(searches)
            return PrecedentSet(
                question_id=game.question_id,
                precedents=precedents,
                source_model=client.model,
                cost_usd=cost,
                searches_used=searches,
                created_at=created_at,
            )
        messages = [
            *messages,
            Message("assistant", result.text or "(no text)"),
            Message("user", _STRICTER),
        ]
    snippet = last_text[:300] if last_text.strip() else "(empty response)"
    raise PrecedentSearchError(
        f"no parseable precedents after {max_retries + 1} attempts. "
        f"First 300 chars of the last response: {snippet!r}"
    )
