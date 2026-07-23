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
    "You did not return a usable JSON object. Reply now with ONLY the JSON object "
    '{"reference_class": ..., "sessions_at_risk": ..., "precedents": [...]} — '
    "no preamble, no notes, no code fences, no commentary."
)


class PrecedentSearchError(RuntimeError):
    """The model returned no parseable precedent set."""


def _system_prompt() -> str:
    return (
        "You build the OUTSIDE VIEW for a forecasting question — a reference class of PRIOR "
        "COMPARABLE DECISIONS. The reference class is SESSIONS-AT-RISK, not notable outcomes: "
        "FIRST identify the full POPULATION of decision opportunities (e.g. every session of the "
        "same body at which this matter was on the agenda) from a stated start date; THEN place "
        "each. **Sessions that decided NOTHING are part of the class** — place them in the "
        "no-action band. Do not list only the dramatic outcomes; that is selection bias.\n"
        "For each decision opportunity give: what happened (including 'no new action'), its date, "
        "a source citation, a placement on the current 0-100 continuum, one line of reasoning, and "
        "whether it is ex-ante codable or hindsight-coded. Cite a real source; never invent one.\n"
        "State the population: `reference_class` (the population definition + start date) and "
        "`sessions_at_risk` (the total count of decision opportunities from the records). If you "
        "CANNOT fully source the enumeration, set `sessions_at_risk` to null so it is reported as "
        "INCOMPLETE rather than a base rate on a biased sample.\n"
        "These are PROPOSALS for a human to ratify — do not overstate confidence.\n"
        "CRITICAL: reply with ONLY one JSON object and nothing else — no preamble, no notes, no "
        "code fences. Shape:\n"
        '{"reference_class": "...", "sessions_at_risk": <int or null>, "precedents": '
        '[{"id": "...", "what_happened": "...", "date": "YYYY-MM", "source": "...", '
        '"proposed_placement": <0-100>, "reasoning": "one line", "ex_ante_codable": true|false}]}'
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
    parts.append(
        "\nEnumerate the population of decision opportunities (sessions-at-risk) FIRST, including "
        "the ones that decided nothing, then return the JSON object."
    )
    return "\n".join(parts)


def _extract_top_json(text: str) -> Any:
    """The top-level JSON of the model reply (object or array), tolerating a preamble before/after
    the JSON and ```json fences. Prefers the whole object (which carries the population metadata)
    before falling back to a bare array (D30, D30.1). Returns None if nothing parses."""
    for candidate in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        cand = candidate.strip()
        chunks = [cand]
        obj = _OBJECT.search(cand)
        if obj is not None:
            chunks.append(obj.group(0))
        arr = _ARRAY.search(cand)
        if arr is not None:
            chunks.append(arr.group(0))
        for chunk in chunks:
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    return None


def _parse_response(text: str) -> tuple[list[Precedent], str, int | None]:
    """Parse a model reply into ``(precedents, reference_class, sessions_at_risk)`` (raises if the
    precedents cannot be found). Accepts the wrapper object, a bare array, or a single object."""
    top = _extract_top_json(text)
    if top is None:
        raise PrecedentSearchError("no JSON object or array in the model response")
    reference_class = ""
    sessions_at_risk: int | None = None
    if isinstance(top, list):
        raw = top
    elif isinstance(top, dict) and isinstance(top.get("precedents"), list):
        raw = top["precedents"]
        reference_class = str(top.get("reference_class") or "")
        val = top.get("sessions_at_risk")
        sessions_at_risk = int(val) if isinstance(val, int | float) else None
    elif isinstance(top, dict):
        raw = [top]  # a single precedent object
    else:
        raise PrecedentSearchError("unexpected JSON shape in the model response")
    return _build_precedents(raw), reference_class, sessions_at_risk


def parse_precedents(text: str) -> list[Precedent]:
    """Parse a model response into unratified :class:`Precedent` proposals (raises if none)."""
    return _parse_response(text)[0]


def _build_precedents(raw: list[Any]) -> list[Precedent]:
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
            precedents, reference_class, sessions_at_risk = _parse_response(result.text)
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
                reference_class=reference_class,
                sessions_at_risk=sessions_at_risk,
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
