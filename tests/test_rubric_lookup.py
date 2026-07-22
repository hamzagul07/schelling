"""Rubric resolution from the committed grading file at render time (Session 24, D24).

The formalizer does not embed a rubric and sealed records can never be regenerated, so
``schelling report`` looks up ``GRADING-<question_id>.md`` and parses its machine-readable
``ResolutionRubric`` block. Tests: the lookup path, embedded-wins precedence, the unchanged
missing-rubric path, determinism, and that resolution never modifies a record or its hash.
"""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from schelling.cli import _resolve_rubric
from schelling.mc.monte_carlo import inputs_hash
from schelling.report.render import render
from schelling.report.rubric_lookup import grading_path, lookup_rubric, parse_rubric_block
from schelling.schemas.forecast import Ensemble, ForecastRecord
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor
from schelling.schemas.stakeholders import TriangularEstimate as T
from schelling.solver.config import SolverConfig

_GRADING_MD = """# GRADING — Q-T

Prose about the rubric.

```json
{
  "resolution_criteria": "the event",
  "adjudicating_sources": ["a source"],
  "outcome_mapping": "map the outcome",
  "grading_formula": "|median - actual|",
  "bands": [
    {"lo": 0, "hi": 49, "label": "the low band"},
    {"lo": 50, "hi": 100, "label": "the high band"}
  ]
}
```
"""


def _game(*, rubric: ResolutionRubric | None) -> GameSpec:
    return GameSpec(
        question_id="Q-T",
        frozen_at="2026-07-22",
        continuum=Continuum(label="sev", anchor_0="low end", anchor_100="high end"),
        template="committee_vote",
        horizon="one decision",
        actors=[
            Actor(
                id="a",
                name="A",
                position=T(low=5, mode=20, high=40),
                salience=T(low=80, mode=90, high=97),
                capability=T(low=90, mode=100, high=100),
            ),
            Actor(
                id="b",
                name="B",
                position=T(low=55, mode=70, high=85),
                salience=T(low=40, mode=55, high=70),
                capability=T(low=40, mode=50, high=60),
            ),
        ],
        resolution_rubric=rubric,
    )


def _record_dict(*, rubric: ResolutionRubric | None) -> dict[str, Any]:
    rec = ForecastRecord(
        question_id="Q-T",
        run_id="Q-T-mc-s0",
        engine_version="deadbeef",
        inputs_hash="0" * 64,
        seed=0,
        model="compromise",
        ensemble=Ensemble(median=30.0, mean=30.0, p10=15.0, p90=48.0, n_draws=6),
        game=_game(rubric=rubric),
        outcome_distribution=[10.0, 20.0, 30.0, 35.0, 40.0, 48.0],
    )
    return cast("dict[str, Any]", json.loads(rec.model_dump_json()))


# --------------------------------------------------------------- parsing + lookup
def test_parse_rubric_block_reads_bands() -> None:
    rubric = parse_rubric_block(_GRADING_MD)
    assert rubric is not None
    assert [b.label for b in rubric.bands] == ["the low band", "the high band"]


def test_parse_rubric_block_none_when_absent_or_invalid() -> None:
    assert parse_rubric_block("no json here") is None
    assert parse_rubric_block("```json\n{not valid}\n```") is None
    assert parse_rubric_block('```json\n{"foo": 1}\n```') is None  # not a ResolutionRubric


def test_grading_path_walks_up_from_a_nested_record(tmp_path: Path) -> None:
    (tmp_path / "GRADING-Q-T.md").write_text(_GRADING_MD)
    nested = tmp_path / "runs"
    nested.mkdir()
    assert grading_path("Q-T", nested) == tmp_path / "GRADING-Q-T.md"
    assert grading_path("Q-OTHER", nested) is None


def test_lookup_returns_rubric_and_source(tmp_path: Path) -> None:
    (tmp_path / "GRADING-Q-T.md").write_text(_GRADING_MD)
    found = lookup_rubric("Q-T", tmp_path)
    assert found is not None
    rubric, source = found
    assert source == "GRADING-Q-T.md" and len(rubric.bands) == 2


# --------------------------------------------------------------- _resolve_rubric (CLI glue)
def test_resolve_injects_when_no_embedded_rubric(tmp_path: Path) -> None:
    (tmp_path / "GRADING-Q-T.md").write_text(_GRADING_MD)
    record_path = tmp_path / "runs" / "rec.json"
    record_path.parent.mkdir()
    data = _record_dict(rubric=None)
    record_path.write_text(json.dumps(data))  # on-disk copy to prove it is never rewritten
    before = record_path.read_bytes()

    source = _resolve_rubric(data, record_path)
    assert source == "GRADING-Q-T.md"
    assert data["game"]["resolution_rubric"]["bands"][0]["label"] == "the low band"  # injected
    assert record_path.read_bytes() == before  # the record file on disk is untouched (item 2)


def test_resolve_precedence_embedded_wins(tmp_path: Path) -> None:
    (tmp_path / "GRADING-Q-T.md").write_text(_GRADING_MD)  # a different rubric on disk
    embedded = ResolutionRubric(
        resolution_criteria="embedded",
        adjudicating_sources=["x"],
        outcome_mapping="m",
        grading_formula="f",
        bands=[RubricBand(lo=0, hi=100, label="only band")],
    )
    data = _record_dict(rubric=embedded)
    source = _resolve_rubric(data, tmp_path / "rec.json")
    assert source is None  # embedded rubric wins; no lookup performed
    assert data["game"]["resolution_rubric"]["resolution_criteria"] == "embedded"  # not overwritten


def test_resolve_none_when_no_grading_file(tmp_path: Path) -> None:
    data = _record_dict(rubric=None)
    assert _resolve_rubric(data, tmp_path / "rec.json") is None


def test_resolve_ignores_non_forecast_artifacts(tmp_path: Path) -> None:
    (tmp_path / "GRADING-Q-T.md").write_text(_GRADING_MD)
    assert _resolve_rubric({"game": {}, "assumptions": []}, tmp_path / "d.json") is None


# --------------------------------------------------------------- render behaviour
def test_render_missing_rubric_path_unchanged() -> None:
    # No rubric, no lookup source -> standard layout (no narrative sections).
    data = _record_dict(rubric=None)
    html = render(data)
    assert "Reading</h2>" not in html and ">Headline<" in html


def test_render_states_looked_up_source_and_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "GRADING-Q-T.md").write_text(_GRADING_MD)
    data = _record_dict(rubric=None)
    source = _resolve_rubric(data, tmp_path / "runs" / "rec.json")
    a = render(data, rubric_source=source)
    b = render(data, rubric_source=source)
    assert a == b  # byte-identical
    assert "Band-probability strip" in a and "Weighted actor positions" in a
    assert "resolved at render time from GRADING-Q-T.md" in a


def test_render_states_embedded_source() -> None:
    embedded = ResolutionRubric(
        resolution_criteria="c",
        adjudicating_sources=["s"],
        outcome_mapping="m",
        grading_formula="f",
        bands=[RubricBand(lo=0, hi=100, label="only")],
    )
    html = render(_record_dict(rubric=embedded))  # rubric_source defaults to None -> embedded
    assert "embedded in the record" in html


# --------------------------------------------------------------- committed grading files (D24.4)
_REPO_ROOT = Path(__file__).parent.parent


def _prose_ranges(mapping: str) -> list[tuple[int, int]]:
    """The band boundaries stated in the ``outcome_mapping`` prose (``lo-hi`` before a ; or .)."""
    return [(int(a), int(b)) for a, b in re.findall(r"(\d{1,3})\s*-\s*(\d{1,3})(?=[;.])", mapping)]


@pytest.mark.parametrize("qid", ["Q-2026-USIRAN-STAGE2", "Q-2026-IAEA-SEP"])
def test_committed_grading_bands_match_outcome_mapping_prose(qid: str) -> None:
    """The structured ``bands`` array and the canonical ``outcome_mapping`` prose must state the
    same seven boundaries — so the two representations can never silently drift (D24.4). A future
    edit to one that does not match the other fails here."""
    rubric = parse_rubric_block((_REPO_ROOT / f"GRADING-{qid}.md").read_text())
    assert rubric is not None and rubric.bands
    band_ranges = [(int(b.lo), int(b.hi)) for b in rubric.bands]
    assert band_ranges == _prose_ranges(rubric.outcome_mapping)
    assert band_ranges[0][0] == 0 and band_ranges[-1][1] == 100  # tile 0-100
    assert all(hi + 1 == nlo for (_, hi), (nlo, _) in itertools.pairwise(band_ranges))  # contiguous


# --------------------------------------------------------------- hash safety (item 3, 5)
def test_attaching_rubric_and_non_voting_leaves_hash_unchanged() -> None:
    cfg = SolverConfig(seed=42)
    base = _game(rubric=None)
    rubric = parse_rubric_block(_GRADING_MD)
    assert rubric is not None
    enriched = base.model_copy(update={"resolution_rubric": rubric, "non_voting_actor_ids": ["b"]})
    # The rubric and the display coding are both excluded from the hash (D22.2 / D23.2).
    assert inputs_hash(base, cfg) == inputs_hash(enriched, cfg)
