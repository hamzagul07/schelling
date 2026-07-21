"""Prompt construction for the formalizer.

The system prompt embeds CLAUDE.md rule (f) verbatim and requires the ``assumptions`` section.
Facts (situation text + sources) and concepts (template cards + index chunks) are delimited so
the model can never mistake a retrieved concept for a real-world fact.
"""

from __future__ import annotations

# CLAUDE.md rule 6 (f), embedded VERBATIM in every formalize prompt.
RULE_F = (
    "The knowledge index is a concepts library ONLY. Retrieval may inform which game template "
    "applies and how to reason about structure; it is NEVER a source of facts, actors, payoffs, "
    "capabilities, or evidence about the real world. Every real-world claim in a GameSpec must "
    "trace to user-supplied situation text or sources."
)

_SCHEMA = """Return ONLY a single JSON object (no prose, no markdown fences) of the form:

{
  "game": {
    "question_id": "Q-...-SHORTSLUG",
    "frozen_at": "YYYY-MM-DD",
    "continuum": {"label": "...", "anchor_0": "what 0 means", "anchor_100": "what 100 means"},
    "actors": [
      {
        "id": "snake_case_id",
        "name": "Readable name",
        "position": {"low": <0-100>, "mode": <0-100>, "high": <0-100>},
        "salience":  {"low": <0-100>, "mode": <0-100>, "high": <0-100>},
        "capability":{"low": <0-100>, "mode": <0-100>, "high": <0-100>},
        "evidence": [{"source": "<supplied text/source>", "date": "YYYY-MM-DD",
                      "note": "quote or point to the supplied text"}]
      }
    ],
    "template": "one of the template names below",
    "horizon": "one_shot | repeated | ...",
    "notes": "brief framing notes"
  },
  "assumptions": [
    {"statement": "anything you asserted that the supplied text/sources do NOT establish",
     "why": "what evidence was missing that forced the assumption"}
  ],
  "template_classification": {
    "template": "same template name",
    "rationale": "why this template fits the situation's structure",
    "template_cards": ["cited card name", "..."],
    "index_chunks": ["cited lecture ref", "..."]
  }
}

Rules for the numbers and evidence:
- position, salience, capability are on a 0-100 scale (Policon procedure: strongest actor's
  capability = 100, others proportional). Use (low, mode, high) triangular ranges to express
  uncertainty; a confident point estimate is low == mode == high.
- Every actor and every evidence note MUST trace to the SITUATION or SOURCES below. If you
  cannot cite supplied text for a claim, do NOT invent a source — record it in assumptions.
- The CONCEPTUAL GROUNDING section is the concepts library. Use it ONLY to pick the template
  and reason about structure. Never copy a fact, actor, number, or place name from it into the
  game or into any evidence note."""


_SEARCH_GUIDANCE = (
    "Before drafting, you MAY use the web_search tool to find current sources for this situation "
    "(recent positions, capabilities, statements). Anything you fetch is EVIDENCE, on the same "
    "footing as the supplied SOURCES: you may cite a fetched page in an evidence note, and you "
    "SHOULD prefer a fetched citation over an assumption. Prefer a few authoritative primary "
    "sources (official statements, filings, primary reporting) over many secondary ones, and cite "
    "the passage you actually rely on. This does NOT relax the rule above — the concepts library "
    "is still never a source of facts. Finish by returning the JSON object."
)


def build_system_prompt(*, search: bool = False) -> str:
    """The formalizer system prompt: rule (f) verbatim + the required output contract.

    With ``search=True`` a paragraph is added telling the model that web-search results are
    evidence (citable like supplied sources), while the concepts-library rule is unchanged.
    """
    search_block = f"{_SEARCH_GUIDANCE}\n\n" if search else ""
    return (
        "You are the formalizer for an open, deterministic strategic-forecasting engine. You "
        "turn a described situation into a formal multilateral-bargaining game specification for "
        "a math solver. You STRUCTURE the problem; you never predict an outcome or a probability "
        "— the solver does that.\n\n"
        "NON-NEGOTIABLE RULE (verbatim):\n"
        f"{RULE_F}\n\n"
        "You MUST include an explicit assumptions[] list for anything you assert that is not "
        "established by the supplied situation text or sources. If in doubt, add an assumption "
        "rather than fabricate evidence.\n\n"
        f"{search_block}"
        f"{_SCHEMA}"
    )


def _format_sources(sources: dict[str, str]) -> str:
    if not sources:
        return "(none provided)"
    return "\n\n".join(f"[source: {name}]\n{text.strip()}" for name, text in sources.items())


def build_user_prompt(
    situation_text: str,
    sources: dict[str, str],
    template_cards: list[str],
    index_chunks: list[str],
) -> str:
    """Assemble the user message: facts first (usable), concepts last (structure only)."""
    cards = "\n".join(f"- {c}" for c in template_cards) or "(none)"
    chunks = "\n".join(f"- {c}" for c in index_chunks) or "(none)"
    return (
        "=== SITUATION (facts you MAY use) ===\n"
        f"{situation_text.strip()}\n\n"
        "=== SOURCES (additional facts you MAY use) ===\n"
        f"{_format_sources(sources)}\n\n"
        "=== CONCEPTUAL GROUNDING (concepts library — NOT facts; use ONLY to choose the "
        "template and reason about structure) ===\n"
        f"Template cards:\n{cards}\n\n"
        f"Relevant lecture passages (concepts only):\n{chunks}\n\n"
        "Now produce the JSON object."
    )
