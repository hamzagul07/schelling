"""The dossier's NARRATIVE half: one tightly-constrained LLM call (Session 26, D26.2).

The hard wall between COMPUTED and NARRATIVE: the model writes prose with ``{{tags}}`` for every
model quantity and never emits a bare numeral for one. The assembler resolves the tags from record;
generation is rejected and retried if an unresolved tag or an invented model numeral survives. Every
factual world-claim must cite a fetched source (formalizer-style), and the concepts firewall applies
unchanged. The narrative is not deterministic — its own SHA-256, model, and cost are recorded.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from schelling.formalizer.client import LLMClient, Message, cost_usd, search_cost_usd
from schelling.formalizer.firewall import scan_text
from schelling.report.bands import map_bands
from schelling.report.svg import format_share
from schelling.schemas.forecast import ForecastRecord

_TAG = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
# A model quantity the narrative must express as a {{tag}}, never as a bare numeral: a percentage
# (other than the fixed 80% CI level) or a model term glued to a number.
_PERCENT = re.compile(r"\b\d+(?:\.\d+)?\s*%")
_MODEL_NUM = re.compile(
    r"\b(?:median|mean|probability|settlement|interval|expected|forecast)\b[^.]{0,24}?\b\d",
    re.IGNORECASE,
)
_CI_LEVEL = (
    "80%"  # the fixed confidence level is methodology, not a model output — allowed verbatim
)


@dataclass(frozen=True)
class NarrativeSections:
    """The model-written sections, keyed by slot; each is source-cited, tag-only for quantities."""

    sections: dict[str, str]
    model: str
    input_tokens: int
    output_tokens: int
    searches_used: int
    cost_usd: float
    sha256: str


def build_tag_values(record: ForecastRecord) -> dict[str, str]:
    """The quantities the narrative may reference by tag, resolved from the record (D26.2)."""
    e = record.ensemble
    readout = map_bands(record)
    vals: dict[str, str] = {
        "median": f"{e.median:.0f}",
        "median1": f"{e.median:.1f}",
        "mean": f"{e.mean:.0f}",
        "p10": f"{e.p10:.0f}",
        "p90": f"{e.p90:.0f}",
        "ci80": f"{e.p10:.0f} to {e.p90:.0f}",
        "n_draws": str(e.n_draws),
        "model": record.model,
    }
    if readout.modal_band is not None:
        vals["modal_band"] = readout.modal_band.label
        modal = next((bp.probability for bp in readout.per_band if bp.is_modal), 0.0)
        vals["modal_share"] = format_share(modal)
    if readout.median_band is not None:
        vals["median_band"] = readout.median_band.label
    return vals


def resolve_tags(text: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Replace ``{{tag}}`` with resolved values; return (resolved_text, unresolved_tag_names)."""
    unresolved: list[str] = []

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in values:
            return values[key]
        unresolved.append(key)
        return m.group(0)

    return _TAG.sub(sub, text), unresolved


def invented_numerals(raw_text: str) -> list[str]:
    """Bare model-quantity numerals in the raw narrative (a percent that is not the CI level, or a
    model term glued to a number) — these must have been ``{{tags}}`` (D26.2)."""
    stripped = _TAG.sub("", raw_text)  # a tag's own name never contains a digit, so this is safe
    hits = [
        m.group(0).strip() for m in _PERCENT.finditer(stripped) if m.group(0).strip() != _CI_LEVEL
    ]
    hits += [m.group(0) for m in _MODEL_NUM.finditer(stripped)]
    return hits


def validate_narrative(raw_text: str, values: dict[str, str]) -> list[str]:
    """Reasons to reject a generation: an unresolved tag or an invented model numeral (D26.2)."""
    _, unresolved = resolve_tags(raw_text, values)
    errs = [f"unresolved tag {{{{{t}}}}}" for t in dict.fromkeys(unresolved)]
    errs += [f"invented model numeral {n!r}" for n in invented_numerals(raw_text)]
    return errs


def narrative_sha256(sections: dict[str, str]) -> str:
    """A stable SHA-256 over the model-written sections — the narrative's commitment (D26.4)."""
    canonical = "\n\x1e".join(f"{k}\x1f{sections[k]}" for k in sorted(sections))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# The five NARRATIVE slots (item 3): everything else in the dossier is COMPUTED.
SLOTS = ("history", "present_state", "interpretation", "enforceability", "limitations")
_SLOT_MARK = re.compile(r"\[\[(\w+)\]\]\s*(.*?)(?=\[\[\w+\]\]|\Z)", re.DOTALL)
_MAX_NARRATIVE_TOKENS = 4000


class NarrativeRejectedError(RuntimeError):
    """The model's narrative failed validation on every attempt (tags / numerals / firewall)."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("narrative rejected: " + "; ".join(errors))
        self.errors = errors


def _parse_sections(text: str) -> dict[str, str]:
    """Split a ``[[slot]] …`` response into ``{slot: prose}`` (unknown slots ignored)."""
    out: dict[str, str] = {}
    for m in _SLOT_MARK.finditer(text):
        slot, body = m.group(1), m.group(2).strip()
        if slot in SLOTS:
            out[slot] = body
    return out


def _system_prompt() -> str:
    return (
        "You are writing the narrative half of a forecasting dossier. STRICT RULES:\n"
        "1. Never write a numeral for any model quantity (median, mean, interval, probability, "
        "settlement point). Instead write a tag the assembler resolves: {{median}}, {{ci80}}, "
        "{{modal_band}}, {{modal_share}}, {{median_band}}, {{mean}}, {{p10}}, {{p90}}, "
        "{{n_draws}}, {{model}}. The only bare percentage you may write is the 80% confidence "
        "level.\n"
        "2. Every factual claim about the world must cite a fetched source inline, e.g. "
        "(Reuters, 2026-06-10). Do not invent facts, sources, dates, or figures.\n"
        "3. Concept-library ideas may inform how you STRUCTURE the enforceability analysis, but "
        "never state a concept phrase as a fact. Analysis only — never a defection playbook.\n"
        "4. Return exactly these sections, each introduced by its marker on its own line:\n"
        "[[history]] [[present_state]] [[interpretation]] [[enforceability]] [[limitations]]\n"
        "Write measured, sourced prose. No headings other than the markers."
    )


def _user_prompt(situation_text: str, sources_text: str, concepts_text: str) -> str:
    parts = [
        "SITUATION (the only provenance for world-facts; cite sources within it):",
        situation_text.strip(),
        "\nFETCHED SOURCES (evidence you may cite):",
        sources_text.strip() or "(none)",
    ]
    if concepts_text.strip():
        parts += [
            "\nCONCEPT FRAMING (for structuring the enforceability analysis ONLY — never quote as "
            "fact):",
            concepts_text.strip(),
        ]
    parts.append(
        "\nWrite the five sections. Use {{tags}} for every model quantity; the assembler resolves "
        "them."
    )
    return "\n".join(parts)


def _correction(errors: list[str]) -> str:
    return (
        "Your draft was rejected for: "
        + "; ".join(errors[:8])
        + ". Rewrite all five sections. Replace every model numeral with the correct {{tag}}, "
        "remove any invented figure or unsupported claim, and keep the [[slot]] markers."
    )


def generate_narrative(
    client: LLMClient,
    record: ForecastRecord,
    *,
    situation_text: str,
    sources_text: str = "",
    concepts_text: str = "",
    search: bool = False,
    max_searches: int = 5,
    max_retries: int = 2,
) -> NarrativeSections:
    """One constrained LLM call (with bounded retries) producing the validated narrative sections.

    Rejects and retries a generation whose sections carry an unresolved tag, an invented model
    numeral, or a concept-library leak (D26.2). Raises :class:`NarrativeRejectedError` if every
    attempt fails. The client is any :class:`LLMClient` — production or a replay client in tests.
    """
    values = build_tag_values(record)
    allowed = f"{situation_text}\n{sources_text}"
    messages = [Message("user", _user_prompt(situation_text, sources_text, concepts_text))]
    errors: list[str] = []
    for _attempt in range(max_retries + 1):
        result = client.complete(
            _system_prompt(),
            messages,
            _MAX_NARRATIVE_TOKENS,
            search=search,
            max_searches=max_searches,
        )
        sections = _parse_sections(result.text)
        errors = []
        for slot in SLOTS:
            if slot not in sections:
                errors.append(f"missing section [[{slot}]]")
                continue
            errors += [f"[{slot}] {e}" for e in validate_narrative(sections[slot], values)]
        errors += [
            f"concept leak {frag!r}"
            for frag in scan_text(" ".join(sections.values()), allowed, concepts_text)
        ]
        if not errors:
            cost = cost_usd(client.model, result.input_tokens, result.output_tokens)
            cost += search_cost_usd(result.searches_used)
            return NarrativeSections(
                sections={s: sections[s] for s in SLOTS},
                model=client.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                searches_used=result.searches_used,
                cost_usd=cost,
                sha256=narrative_sha256({s: sections[s] for s in SLOTS}),
            )
        messages = [
            *messages,
            Message("assistant", result.text),
            Message("user", _correction(errors)),
        ]
    raise NarrativeRejectedError(errors)


def render_narrative_slot(sections: dict[str, str], slot: str, values: dict[str, str]) -> str:
    """Resolve a slot's tags to their computed values for display (D26.2)."""
    resolved, _ = resolve_tags(sections.get(slot, ""), values)
    return resolved
