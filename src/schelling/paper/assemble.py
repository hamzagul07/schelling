"""Deterministic paper assembly (Session 15, D15.1).

Concatenate the eleven approved draft sections (``paper/draft/00-abstract.md`` …
``10-conclusion.md``) in order into ``paper/DRAFT.md``, resolving every ``[E-tag]`` citation inline
to its value from ``paper/EVIDENCE.md`` with a provenance footnote, placing the figures at their
section anchors, and appending the bibliography skeleton. The draft prose is treated as approved
verbatim — assembly never edits it, it only resolves citations and inserts figures/footnotes.

Pure function of the on-disk inputs: no wall-clock, sorted file order, stable dict order → the same
inputs produce a byte-identical ``DRAFT.md`` every run (deterministic + idempotent, rule 2).
Any ``E-tag`` that EVIDENCE.md cannot resolve becomes a visible ``**TODO(E-tag)**`` in the text and
is reported, never silently dropped or invented.
"""

from __future__ import annotations

import re
from pathlib import Path

_TAG = re.compile(r"E-[A-Za-z0-9_-]+")
_GROUP = re.compile(r"( ?)\[([^\[\]]*E-[A-Za-z0-9_-]+[^\[\]]*)\]")
# A sentence ends at ; : newline, or a . ! ? followed by whitespace + a capital — the last rule
# ignores abbreviation dots ("et al. 2006", "e.g.") so the current-sentence window is not truncated.
_SENTENCE_END = re.compile(r"[.!?]\s+(?=[A-Z])")

# A resolved value renders as an inline parenthetical only when it is a *measured quantity* — i.e.
# it begins with a digit or a numeric delimiter (sign, paren, bracket). A value that begins with a
# letter is a verdict, boolean, or description (FAILED, True, PENDING, a method description) and
# resolves FOOTNOTE-ONLY, never as an inline "(FAILED)"/"(True)" (Session 52, extends D16.2).
_NUMERIC_LEAD = re.compile(r"^\s*[-+(\[]*\s*\.?\d")


def _is_numeric_value(value: str) -> bool:
    """True when a resolved value reads as a number/measurement, False for a verdict/description."""
    return bool(_NUMERIC_LEAD.match(value))


def _current_sentence(prefix: str) -> str:
    """The prose of the sentence that ``prefix`` (text before a citation) ends in."""
    cut = max(prefix.rfind(";"), prefix.rfind(":"), prefix.rfind("\n"))
    for m in _SENTENCE_END.finditer(prefix):
        cut = max(cut, m.start())
    return prefix[cut + 1 :]


# Figures placed after the section whose evidence they illustrate (drafts carry no anchors).
_FIG_AFTER: dict[str, list[tuple[str, str]]] = {
    "03-fair-fight.md": [
        (
            "fig_deu_error_histogram.svg",
            "Figure 1. Absolute-error distribution of the challenge model on the 351 DEU issues — "
            "bimodal, with pole-to-pole misses.",
        ),
        (
            "fig_challenge_vs_compromise.svg",
            "Figure 2. Absolute-error distributions compared: challenge (primary) vs the "
            "compromise weighted mean.",
        ),
    ],
    "04-successor-search.md": [
        (
            "fig_leaderboard.svg",
            "Figure 3. Successor-search leaderboard — neither candidate beats the compromise "
            "mean on the untouched TEST split.",
        ),
        (
            "fig_r1_split.svg",
            "Figure 4. The pre-registered 40/30/30 train/dev/TEST split, committed before fitting.",
        ),
    ],
}


def parse_evidence(evidence_md: str) -> dict[str, dict[str, str]]:
    """Parse EVIDENCE.md's table into ``tag -> {value, source, prov}``."""
    rows: dict[str, dict[str, str]] = {}
    for line in evidence_md.splitlines():
        if not line.startswith("| E-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        rows[cells[0]] = {
            "value": cells[3],
            "source": cells[4].strip("`"),
            "prov": cells[5].strip("`"),
        }
    return rows


def _lookup(tag: str, evidence: dict[str, dict[str, str]]) -> dict[str, str] | None:
    """Resolve a tag exactly, or as a family prefix (e.g. E-LEDGER -> E-LEDGER-*)."""
    if tag in evidence:
        return evidence[tag]
    family = {k: v for k, v in evidence.items() if k.startswith(tag + "-")}
    if family:
        first = next(iter(family.values()))
        return {
            "value": ", ".join(v["value"] for v in family.values()),
            "source": first["source"],
            "prov": "family: " + ", ".join(family),
        }
    return None


def _resolve_tags(
    text: str, evidence: dict[str, dict[str, str]]
) -> tuple[str, dict[str, dict[str, str]], list[str]]:
    """Replace every bracketed ``[…E-tag…]`` with resolved values + footnote markers."""
    used: dict[str, dict[str, str]] = {}
    todos: list[str] = []
    marked: set[str] = set()  # tags whose footnote marker was already emitted (dedupe, Session 52)

    def repl_group(m: re.Match[str]) -> str:
        space, inner = m.group(1), m.group(2)
        marks: list[str] = []

        def repl_tag(tm: re.Match[str]) -> str:
            tag = tm.group(0)
            item = _lookup(tag, evidence)
            if item is None:
                if tag not in todos:
                    todos.append(tag)
                return f"**TODO({tag})**"
            used[tag] = item
            marks.append(tag)
            return item["value"]

        resolved = _TAG.sub(repl_tag, inner)
        # One footnote per distinct E-tag (Session 52): emit the ``[^ev-tag]`` marker only on the
        # tag's FIRST citation. A repeat shows its value but adds no second footnote — pandoc
        # renders a re-referenced footnote as a duplicate, so we dedupe at the source.
        fresh = [t for t in dict.fromkeys(marks) if t not in marked]
        footnotes = "".join(f"[^ev-{t}]" for t in fresh)
        marked.update(fresh)
        if len(_TAG.findall(inner)) == 1 and marks:
            value = used[marks[0]]["value"]
            # (a) D16.2: the value already appears in the current sentence's prose -> footnote-only.
            sentence = _current_sentence(m.string[: m.start()])
            in_prose = re.search(r"(?<![\w.])" + re.escape(value) + r"(?![\w.])", sentence)
            # (b) Session 52: a non-numeric value (verdict/boolean/description) -> footnote-only,
            #     never an inline "(FAILED)"/"(True)" parenthetical.
            if in_prose or not _is_numeric_value(value):
                return footnotes
        return f"{space}({resolved}){footnotes}"

    return _GROUP.sub(repl_group, text), used, todos


def assemble(repo_root: Path) -> tuple[str, list[str], list[str]]:
    """Assemble DRAFT.md. Returns ``(markdown, todo_tags, missing_inputs)``."""
    paper = repo_root / "paper"
    draft_dir = paper / "draft"
    missing: list[str] = []
    files = sorted(draft_dir.glob("[0-9][0-9]-*.md")) if draft_dir.is_dir() else []
    if len(files) != 11:
        missing.append(f"expected 11 draft files in paper/draft/, found {len(files)}")

    evidence_path = paper / "EVIDENCE.md"
    if not evidence_path.exists():
        missing.append("paper/EVIDENCE.md not found — run `schelling paper-evidence` first")
        evidence: dict[str, dict[str, str]] = {}
    else:
        evidence = parse_evidence(evidence_path.read_text())

    parts = [
        "<!-- Generated by `schelling paper-assemble` — DO NOT edit by hand. "
        "Edit paper/draft/*.md and paper/EVIDENCE.md, then regenerate. -->",
        "",
    ]
    for f in files:
        parts.append(f.read_text().rstrip())
        for fig, caption in _FIG_AFTER.get(f.name, []):
            fig_path = paper / "figures" / fig
            if not fig_path.exists():
                missing.append(f"figure missing: paper/figures/{fig}")
            parts.append("")
            parts.append(f"![{caption}](figures/{fig})")
            parts.append("")
            parts.append(f"*{caption}*")
        parts.append("")

    body = "\n".join(parts)
    resolved, used, todos = _resolve_tags(body, evidence)

    bib_path = paper / "BIBLIOGRAPHY.md"
    bib = (
        bib_path.read_text().rstrip() if bib_path.exists() else "## References (skeleton)\n\n_TODO_"
    )
    if not bib_path.exists():
        missing.append("paper/BIBLIOGRAPHY.md not found")

    footnotes = [
        "",
        "## Provenance footnotes",
        "",
        "> Every citation above resolves to a value regenerated by `schelling "
        "paper-evidence`; the source artifact and provenance stamp follow each.",
        "",  # blank line so the first definition is not read as a lazy blockquote continuation
    ]
    for tag, item in used.items():
        footnotes.append(
            f"[^ev-{tag}]: **{tag}** = {item['value']} · source "
            f"`{item['source']}` · `{item['prov']}`"
        )

    draft = resolved.rstrip() + "\n\n" + bib + "\n" + "\n".join(footnotes) + "\n"
    return draft, todos, missing
