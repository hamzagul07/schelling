"""Resolve a question's ResolutionRubric from its committed grading file when a record embeds
none (``GRADING-<question_id>.md``, Session 24, D24.1).

The formalizer does not add a rubric to the game, and sealed records can never be regenerated — but
the rubric is committed, byte-frozen, in the grading file. At *render time* (read-only, never
touching the record) we look up that file, parse its machine-readable ``ResolutionRubric`` block,
and hand it to the report so the two-audience narrative renders. An embedded rubric always wins
over a looked-up one (the caller checks that first).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from schelling.schemas.question import ResolutionRubric

# The machine-readable rubric is a ```json … ``` fenced block in the grading file.
_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def grading_path(question_id: str, start: Path) -> Path | None:
    """Find ``GRADING-<question_id>.md`` by walking up from ``start`` and the cwd to the root.

    Grading files live at the repo root; a record may sit anywhere beneath it (``runs/``,
    ``analyses/``), so we search every ancestor directory, nearest first.
    """
    name = f"GRADING-{question_id}.md"
    roots: list[Path] = []
    for base in (start, Path.cwd()):
        p = base.resolve()
        while True:
            roots.append(p)
            if p.parent == p:
                break
            p = p.parent
    for directory in dict.fromkeys(roots):  # dedup, preserve nearest-first order
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def parse_rubric_block(md_text: str) -> ResolutionRubric | None:
    """The first ```json block that validates as a ``ResolutionRubric`` (else None)."""
    for match in _JSON_BLOCK.finditer(md_text):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        try:
            return ResolutionRubric.model_validate(obj)
        except ValueError:
            continue
    return None


def lookup_rubric(question_id: str, start: Path) -> tuple[ResolutionRubric, str] | None:
    """Resolve ``(rubric, source_filename)`` from the committed grading file, or None if absent."""
    path = grading_path(question_id, start)
    if path is None:
        return None
    rubric = parse_rubric_block(path.read_text())
    if rubric is None:
        return None
    return rubric, path.name
