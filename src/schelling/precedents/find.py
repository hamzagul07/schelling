"""Find prior comparable decisions — the outside view (Session 29, D29.1).

One LLM call (optionally web-searching) that identifies prior decisions of the same body / dyad /
institution / decision type, and for each proposes a placement on the current question's 0-100
continuum with one line of reasoning. Everything is a PROPOSAL — nothing is auto-accepted; a human
ratifies before a precedent becomes evidence or enters the reference-class panel (D29.2).
"""

from __future__ import annotations

import json
import re

from schelling.formalizer.client import LLMClient, Message, cost_usd, search_cost_usd
from schelling.precedents.schemas import PrecedentSet
from schelling.schemas.forecast import Precedent
from schelling.schemas.question import GameSpec

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_MAX_TOKENS = 4000


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
        "Reply with ONLY a JSON array; each element:\n"
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


def parse_precedents(text: str) -> list[Precedent]:
    """Parse a model JSON array into unratified :class:`Precedent` proposals (raises)."""
    m = _JSON_ARRAY.search(text)
    if m is None:
        raise PrecedentSearchError("no JSON array in the model response")
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise PrecedentSearchError(f"unparseable precedent list: {exc}") from exc
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
) -> PrecedentSet:
    """One LLM call producing a :class:`PrecedentSet` of unratified proposals (D29.1)."""
    system = _system_prompt()
    user = _user_prompt(game, sources_text)
    result = client.complete(
        system, [Message("user", user)], _MAX_TOKENS, search=search, max_searches=max_searches
    )
    precedents = parse_precedents(result.text)
    if not precedents:
        raise PrecedentSearchError("no precedents found")
    cost = cost_usd(client.model, result.input_tokens, result.output_tokens)
    cost += search_cost_usd(result.searches_used)
    return PrecedentSet(
        question_id=game.question_id,
        precedents=precedents,
        source_model=client.model,
        cost_usd=cost,
        searches_used=result.searches_used,
        created_at=created_at,
    )
