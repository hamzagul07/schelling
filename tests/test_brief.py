"""The graded-forecast brief (Session 56, D56): refusal on ungraded questions, figure provenance
(every number computed from an artifact, never hand-typed), a generated data-scaled chart,
determinism, and the {{tag}} hard wall (an unresolved tag fails the build)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from schelling.brief.chart import _nice_axis, render_chart
from schelling.brief.data import BriefNotGradedError, gather_brief, slug_for
from schelling.brief.prose import (
    REQUIRED_SLOTS,
    BriefProse,
    BriefProseError,
    parse_prose,
    resolve_prose,
)
from schelling.brief.render import DEFAULT_SITE_URL, build_brief, prose_path, render_page
from schelling.report.svg import _n
from schelling.site.render import DEFAULT_REPO_URL, check_briefs

REPO_ROOT = Path(__file__).resolve().parent.parent
GRADED = "Q-2026-OPEC-SEP"
UNGRADED = "Q-2026-IAEA-SEP"  # sealed with a pre-registered rubric, but no recorded outcome

# Structural HTML tokens that are not figures: viewport initial-scale=1, the "8" of UTF-8, the "256"
# of SHA-256. Everything else in the prose/table must trace to an artifact.
_STRUCTURAL = {"1", "8", "256"}
_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?")
_STYLE = re.compile(r"<style>.*?</style>", re.DOTALL)
_SVG = re.compile(r"<svg.*?</svg>", re.DOTALL)  # chart geometry is computed, verified separately
_SCRIPT = re.compile(r"<script>.*?</script>", re.DOTALL)
_ENTITY = re.compile(r"&#?\w+;")


def _brief_html() -> str:
    _slug, html = render_page(GRADED, REPO_ROOT)
    return html


# --------------------------------------------------------------------------- refusal (item: tests)
def test_refuses_an_ungraded_question() -> None:
    with pytest.raises(BriefNotGradedError):
        gather_brief(UNGRADED, REPO_ROOT)
    with pytest.raises(BriefNotGradedError):
        render_page(UNGRADED, REPO_ROOT)


def test_build_command_refuses_ungraded(tmp_path: Path) -> None:
    with pytest.raises(BriefNotGradedError):
        build_brief(UNGRADED, REPO_ROOT, docs_dir=tmp_path)


# --------------------------------------------------------------------------- figures from artifacts
def test_no_hand_typed_figures() -> None:
    """Every number the brief prints (outside the computed chart/style) traces to a figure."""
    data = gather_brief(GRADED, REPO_ROOT)
    allowed = data.provenance() | _STRUCTURAL
    scrubbed = _ENTITY.sub(" ", _SVG.sub("", _STYLE.sub("", _SCRIPT.sub("", _brief_html()))))
    for token in _NUM.findall(scrubbed):
        assert token in allowed, f"un-sourced number {token!r}"


def test_barrels_invert_the_rubric_not_typed() -> None:
    """The barrels column is the outcome_map inverted — (continuum - intercept)/slope."""
    data = gather_brief(GRADED, REPO_ROOT)
    html = _brief_html()
    for r in data.records:
        implied = round((r.median - data.intercept) / data.slope) * 1000
        assert data.barrels_display(r.median) == f"{implied:,}"
        assert f'<td class="num">{data.barrels_display(r.median)}</td>' in html
    # the exact forecast inverts to 192,000 b/d; the thinnest to 96,000 — computed, not the raw 188
    assert data.barrels_display(66.0) == "192,000"
    assert data.barrels_display(58.0) == "96,000"


def test_outcome_and_citation_come_from_the_grading_file() -> None:
    data = gather_brief(GRADED, REPO_ROOT)
    html = _brief_html()
    assert data.actual_continuum == 66.0 and data.actual_raw == 188.0
    assert data.citation.startswith("https://www.opec.org/")
    assert data.citation in html  # the outcome's source is cited on the page
    # the announced barrels (188,000) and the settlement (66) are the ledger's, resolved via tags
    assert "188,000" in html and data.resolved_date == "2 August 2026"


def test_dates_come_from_the_ledger() -> None:
    """Seal/resolution/grading dates are read from the artifacts, not the reference mock-up."""
    data = gather_brief(GRADED, REPO_ROOT)
    assert data.seal_date == "24 July 2026"  # frozen_at
    assert data.resolved_date == "2 August 2026"  # announcement, from the justification
    assert data.grade_date == "6 August 2026"  # Grading date header


# --------------------------------------------------------------------------- generated chart
def test_chart_is_generated_scaled_and_offline_clean() -> None:
    data = gather_brief(GRADED, REPO_ROOT)
    svg = render_chart(data)
    assert svg == render_chart(data)  # byte-identical
    assert 'role="img"' in svg and "<title>" in svg and "<desc>" in svg
    assert "<script" not in svg and "xmlns" not in svg and "http" not in svg
    # axis bounds are derived from the spread (58..66), NOT the reference's hardcoded 54..70
    plotted = [r.median for r in data.records] + [data.actual_continuum]
    lo, hi, _ticks = _nice_axis(min(plotted), max(plotted))
    assert (lo, hi) == (56.0, 68.0)
    assert ">54</text>" not in svg and ">70</text>" not in svg


def test_chart_marks_are_positioned_from_the_values() -> None:
    """Every mark sits at its forecast's value; the reality rule at the graded value."""
    data = gather_brief(GRADED, REPO_ROOT)
    svg = render_chart(data)
    plotted = [r.median for r in data.records] + [data.actual_continuum]
    lo, hi, _t = _nice_axis(min(plotted), max(plotted))

    def x(v: float) -> str:
        return _n(90.0 + (v - lo) / (hi - lo) * (1100.0 - 90.0))

    for r in data.records:
        assert f'cx="{x(r.median)}"' in svg, f"{r.model}/{r.vintage} not plotted at its median"
    # reality rule is a vertical line at the graded outcome
    assert f'<line x1="{x(data.actual_continuum)}" y1="34.00"' in svg


# --------------------------------------------------------------------------- determinism
def test_render_is_deterministic() -> None:
    assert render_page(GRADED, REPO_ROOT) == render_page(GRADED, REPO_ROOT)


def test_build_writes_identical_bytes(tmp_path: Path) -> None:
    a = build_brief(GRADED, REPO_ROOT, docs_dir=tmp_path / "a").read_text()
    b = build_brief(GRADED, REPO_ROOT, docs_dir=tmp_path / "b").read_text()
    assert a == b


# --------------------------------------------------------------------------- the {{tag}} hard wall
def test_unresolved_tag_fails_the_build() -> None:
    data = gather_brief(GRADED, REPO_ROOT)
    prose = BriefProse({slot: "x" for slot in REQUIRED_SLOTS} | {"standfirst": "see {{no_such}}"})
    with pytest.raises(BriefProseError, match="no_such"):
        resolve_prose(prose, data.tag_values())


def test_missing_slot_fails_the_build() -> None:
    data = gather_brief(GRADED, REPO_ROOT)
    prose = BriefProse({slot: "x" for slot in REQUIRED_SLOTS if slot != "caveats"})
    with pytest.raises(BriefProseError, match="caveats"):
        resolve_prose(prose, data.tag_values())


def test_committed_prose_resolves_with_no_leftover_tags() -> None:
    data = gather_brief(GRADED, REPO_ROOT)
    prose = parse_prose(prose_path(REPO_ROOT, data.slug).read_text())
    resolved = resolve_prose(prose, data.tag_values())
    assert not any("{{" in text for text in resolved.values())
    assert set(REQUIRED_SLOTS) <= set(resolved)


# --------------------------------------------------------------------------- offline + drift
def test_brief_is_offline_clean() -> None:
    """The standalone brief embeds no external resource: no external src=, no <link>, no @import,
    no url(http…). It may cite sources with navigational <a href> links (D31.6-style)."""
    html = _brief_html()
    assert "@import" not in html
    assert not re.search(r'src\s*=\s*"https?:', html)
    assert not re.search(r"url\(\s*https?:", html)
    assert "<link" not in html  # the stylesheet is inlined, not fetched


def test_committed_brief_matches_a_fresh_build() -> None:
    """The committed HTML is exactly what the command regenerates — no drift (D56)."""
    _slug, html = render_page(
        GRADED, REPO_ROOT, repo_url=DEFAULT_REPO_URL, site_url=DEFAULT_SITE_URL
    )
    committed = (REPO_ROOT / "docs" / "briefs" / f"{slug_for(GRADED)}.html").read_text()
    assert committed == html
    assert check_briefs(REPO_ROOT, REPO_ROOT / "docs") == []
