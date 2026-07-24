"""Two-audience narrative report (Session 22): band mapping, layered sections, determinism.

Covers the band-probability arithmetic against a hand-computed fixture, the modal/median bands,
the graceful no-rubric and arithmetic/linear paths, verdict text, byte-identical determinism, and
that a rubric-less record still routes to the unchanged standard layout.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Sequence
from pathlib import Path

from schelling.report import bands as bandmap
from schelling.report.render import (
    _render_forecast_standard,
    render,
    render_forecast,
    render_forecast_narrative,
)
from schelling.report.vocab import load_vocab, phrase_for
from schelling.schemas.forecast import Ensemble, ForecastRecord
from schelling.schemas.question import Continuum, GameSpec, ResolutionRubric, RubricBand
from schelling.schemas.stakeholders import Actor
from schelling.schemas.stakeholders import TriangularEstimate as T

FIXTURES = Path(__file__).parent / "fixtures"

_BANDS = [
    RubricBand(lo=0, hi=24, label="band A"),
    RubricBand(lo=25, hi=49, label="band B"),
    RubricBand(lo=50, hi=74, label="band C"),
    RubricBand(lo=75, hi=100, label="band D"),
]


def _rubric(bands: list[RubricBand]) -> ResolutionRubric:
    return ResolutionRubric(
        resolution_criteria="x",
        adjudicating_sources=["s"],
        outcome_mapping="map",
        grading_formula="score = |median - actual|",
        bands=bands,
    )


def _game(bands: list[RubricBand] | None) -> GameSpec:
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
                position=T(low=5, mode=15, high=30),
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
        resolution_rubric=None if bands is None else _rubric(bands),
    )


def _record(
    draws: Sequence[float], median: float, bands: list[RubricBand] | None
) -> ForecastRecord:
    return ForecastRecord(
        question_id="Q-T",
        run_id="Q-T-mc-s0",
        engine_sha="deadbeef",
        inputs_hash="0" * 64,
        seed=0,
        model="challenge",
        ensemble=Ensemble(
            median=median, mean=median, p10=min(draws), p90=max(draws), n_draws=len(draws)
        ),
        game=_game(bands),
        outcome_distribution=list(draws),
    )


# --------------------------------------------------------------- band mapping (item 1)
def test_band_probabilities_sum_to_one_and_match_hand_computed() -> None:
    draws = [10, 10, 10, 30, 30, 60, 90, 90]  # A:3, B:2, C:1, D:2 of 8
    readout = bandmap.map_bands(_record(draws, median=30.0, bands=_BANDS))
    assert readout.kind == bandmap.BANDED
    probs = [bp.probability for bp in readout.per_band]
    assert probs == [3 / 8, 2 / 8, 1 / 8, 2 / 8]
    assert sum(probs) == 1.0


def test_modal_and_median_bands() -> None:
    draws = [10, 10, 10, 30, 30, 60, 90, 90]
    readout = bandmap.map_bands(_record(draws, median=30.0, bands=_BANDS))
    assert readout.modal_band is not None and readout.modal_band.label == "band A"  # 3/8, the mode
    assert readout.median_band is not None and readout.median_band.label == "band B"  # median 30
    modal = [bp for bp in readout.per_band if bp.is_modal]
    median = [bp for bp in readout.per_band if bp.is_median]
    assert [bp.band.label for bp in modal] == ["band A"]
    assert [bp.band.label for bp in median] == ["band B"]


def test_band_membership_uses_lo_threshold_no_gaps() -> None:
    # A float between the written integer bands (e.g. 24.5) still lands cleanly, in band A.
    readout = bandmap.map_bands(_record([24.5, 49.5], median=24.5, bands=_BANDS))
    assert [bp.probability for bp in readout.per_band] == [0.5, 0.5, 0.0, 0.0]


def test_linear_rubric_degrades_to_arithmetic() -> None:
    readout = bandmap.map_bands(_record([10, 40, 80], median=40.0, bands=[]))
    assert readout.kind == bandmap.LINEAR and readout.per_band == []
    assert "arithmetic" in readout.note.lower()


def test_no_rubric_degrades_gracefully() -> None:
    readout = bandmap.map_bands(_record([10, 40, 80], median=40.0, bands=None))
    assert readout.kind == bandmap.NONE and readout.per_band == []
    assert "no resolution rubric" in readout.note.lower()


def test_band_containing_and_none() -> None:
    assert bandmap.band_containing(30.0, _rubric(_BANDS)).label == "band B"  # type: ignore[union-attr]
    assert bandmap.band_containing(30.0, _rubric([])) is None
    assert bandmap.band_containing(30.0, None) is None


def test_compromise_point_matches_advise_settlement() -> None:
    from schelling.advise.search import _compromise_settlement

    g = _game(_BANDS)
    assert bandmap.compromise_point(g) == _compromise_settlement(g)


# --------------------------------------------------------------- narrative render (item 2, 3)
def test_verdict_names_the_modal_band_with_its_probability() -> None:
    draws = [10] * 7 + [90] * 3  # band A modal at 70%
    html = render_forecast_narrative(_record(draws, median=10.0, bands=_BANDS))
    assert "Most likely: <strong>band A</strong> — 70%" in html
    assert (
        "Verdict" in html and "Reading" in html and "Analyst brief" in html and "Appendix" in html
    )


def test_render_is_deterministic_byte_identical() -> None:
    rec = _record([10, 10, 30, 60, 90], median=30.0, bands=_BANDS)
    assert render_forecast_narrative(rec) == render_forecast_narrative(rec)


def test_dispatch_routes_rubric_records_to_narrative() -> None:
    rec = _record([10, 30, 60], median=30.0, bands=_BANDS)
    assert render_forecast(rec) == render_forecast_narrative(rec)
    assert "Verdict" in render_forecast(rec)


def test_dispatch_keeps_standard_layout_for_no_rubric() -> None:
    # A rubric-less record must render byte-identically to the pre-D22 standard layout.
    rec = _record([10, 30, 60], median=30.0, bands=None)
    assert render_forecast(rec) == _render_forecast_standard(rec)


def test_narrative_says_so_when_no_rubric() -> None:
    # Forced onto the narrative path, a rubric-less record explains the missing rubric.
    html = render_forecast_narrative(_record([10, 30, 60], median=30.0, bands=None))
    assert "No resolution rubric is committed" in html


def test_sources_fetched_appear_in_appendix() -> None:
    data = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    html = render(data)
    assert "Sources fetched (2)" in html
    assert "Board adopts June resolution" in html


# --------------------------------------------------------------- golden + vocabulary
def test_narrative_report_matches_golden() -> None:
    data = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    assert render(data) == (FIXTURES / "report" / "forecast_narrative_report.html").read_text()


def test_position_vocabulary_buckets() -> None:
    v = load_vocab()
    assert phrase_for(5, v.position_fifths) == "at the far low end"
    assert phrase_for(50, v.position_fifths) == "close to the midpoint"
    assert phrase_for(95, v.position_fifths) == "at the far high end"
    assert phrase_for(10, v.position_thirds) == "near the low end"
    assert phrase_for(90, v.position_thirds) == "near the high end"
    assert phrase_for(90, v.salience_thirds) == "a defining issue for it"


# --------------------------------------------------------------- report visuals (Session 23)
def test_band_segments_tile_0_100_and_shares_match_probs() -> None:
    from schelling.report.render import _band_segments

    readout = bandmap.map_bands(
        _record([10, 10, 10, 30, 30, 60, 90, 90], median=30.0, bands=_BANDS)
    )
    segs = _band_segments(readout)
    assert segs[0].lo == 0.0 and segs[-1].hi == 100.0  # tile the full scale
    assert all(a.hi == b.lo for a, b in itertools.pairwise(segs))  # no gaps
    # the strip's shares are exactly the computed band probabilities (item 5)
    assert [s.share for s in segs] == [bp.probability for bp in readout.per_band]
    assert sum(s.modal for s in segs) == 1  # exactly one modal segment


def test_band_strip_svg_is_byte_identical_and_accessible() -> None:
    from schelling.report.palette import load_palette
    from schelling.report.render import _band_segments
    from schelling.report.svg import band_strip

    readout = bandmap.map_bands(
        _record([10, 10, 10, 30, 30, 60, 90, 90], median=30.0, bands=_BANDS)
    )
    segs = _band_segments(readout)
    pal = load_palette()
    kw = dict(median=30.0, p10=10.0, p90=90.0, palette=pal, desc="a strip")
    a = band_strip(segs, **kw)  # type: ignore[arg-type]
    b = band_strip(segs, **kw)  # type: ignore[arg-type]
    assert a == b  # deterministic, byte-identical
    assert 'role="img"' in a and "<title>" in a and "<desc>a strip</desc>" in a  # a11y (item 4)


def test_weighted_actors_flags_non_voting_and_degrades() -> None:
    from schelling.report.palette import load_palette
    from schelling.report.svg import WActor, weighted_actors

    pal = load_palette()
    coded = [WActor("A", 20, 100, False), WActor("B", 80, 50, True)]
    with_flag = weighted_actors(coded, settlement=50.0, palette=pal, desc="d")
    assert "stroke-dasharray" in with_flag and "<desc>d</desc>" in with_flag
    # graceful: with nothing coded non-voting, no dashed ring is drawn
    plain = weighted_actors([WActor("A", 20, 100, False)], settlement=50.0, palette=pal)
    assert "stroke-dasharray" not in plain


def test_palette_loads_two_ramps_from_committed_file() -> None:
    from schelling.report.palette import load_palette

    pal = load_palette()
    assert pal.low_half.startswith("#") and pal.high_half.startswith("#")
    assert pal.low_half != pal.high_half  # two distinct continuum-half ramps


def test_linear_rubric_uses_density_strip_not_band_strip() -> None:
    draws = [float(x) for x in range(0, 100, 5)]
    html = render_forecast_narrative(_record(draws, median=50.0, bands=[]))
    assert "Outcome density strip" in html  # continuous density strip for arithmetic rubrics
    assert "Band-probability strip" not in html


def test_verdict_and_reading_carry_their_figures() -> None:
    html = render_forecast_narrative(_record([10] * 7 + [90] * 3, median=10.0, bands=_BANDS))
    assert "Band-probability strip" in html  # VERDICT strip
    assert "Weighted actor positions" in html  # READING diagram
    assert "Circle area" in html  # the actor-diagram legend


def test_narrative_report_loads_no_external_resources() -> None:
    # The inline SVG figures must not introduce any resource-loading token (offline-clean, D8.4).
    html = render(json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())).lower()
    for token in ("<script", "<link", "src=", "@import", "url("):
        assert token not in html


# --------------------------------------------------------------- verdict calibration + polish (S25)
def test_format_share_caps_at_boundaries() -> None:
    from schelling.report.svg import format_share

    assert format_share(1.0) == ">99%"
    assert format_share(0.995) == ">99%"
    assert format_share(0.99) == "99%"  # exactly 0.99 is not "above 0.99"
    assert format_share(0.5) == "50%"
    assert format_share(0.01) == "1%"  # exactly 0.01 is not "below 0.01"
    assert format_share(0.005) == "<1%"
    assert format_share(0.0) == "<1%"


def test_capped_shares_never_show_zero_or_hundred_in_report() -> None:
    # All draws in one band -> that band ~1.0, the rest 0.0; the strip/table/verdict must cap.
    html = render_forecast_narrative(_record([30.0] * 20, median=30.0, bands=_BANDS))
    assert ">99%" in html and "<1%" in html  # the cap fired for both extremes
    # no band-share cell reads a false certainty
    assert "<td class='num'>100%</td>" not in html and "<td class='num'>0%</td>" not in html


def test_scope_line_always_present() -> None:
    scope = "reflect uncertainty in the stated input ranges only"
    assert scope in render_forecast_narrative(_record([10, 30, 60], median=30.0, bands=_BANDS))
    assert scope in render_forecast_narrative(
        _record([10, 30, 60], median=30.0, bands=[])
    )  # linear
    assert scope in render_forecast_narrative(
        _record([10, 30, 60], median=30.0, bands=None)
    )  # none


def test_short_name_derivation() -> None:
    from schelling.report.render import _derive_short

    assert _derive_short("Subject state (influence only)") == "Subject state"
    assert _derive_short("United States — the pressure bloc") == "United States"
    assert _derive_short("E3 - penholders") == "E3"
    assert (
        _derive_short("Non-aligned swing bloc") == "Non-aligned swing bloc"
    )  # internal hyphen kept


def test_short_names_override_used_in_prose_and_figure_not_table() -> None:
    from schelling.report.render import render_forecast_narrative as rfn

    game = _game(_BANDS).model_copy(
        update={
            "actors": [
                Actor(
                    id="a",
                    name="Aardvark Coalition (the doves)",
                    position=T(low=5, mode=20, high=40),
                    salience=T(low=80, mode=90, high=97),
                    capability=T(low=90, mode=100, high=100),
                ),
                _game(_BANDS).actors[1],
            ],
            "short_names": {"b": "Bees"},
        }
    )
    rec = _record([10, 30, 60], median=30.0, bands=_BANDS).model_copy(update={"game": game})
    html = rfn(rec)
    assert "Aardvark Coalition (the doves)" in html  # full name kept in the stakeholder table
    assert "<strong>Aardvark Coalition</strong> sits" in html  # prose uses the derived short name
    assert "Aardvark Coalition (the doves)</strong> sits" not in html  # not the full name in prose
    assert "<strong>Bees</strong> sits" in html  # the explicit short_names override is used


def test_actor_diagram_legend_uses_fixed_direction_phrases() -> None:
    # The legend must use fixed direction phrases, never truncated anchor prose (D25.4).
    html = render_forecast_narrative(_record([10, 30, 60], median=30.0, bands=_BANDS))
    assert "Amber = the low half (toward 0); teal = the high half (toward 100)." in html
    assert (
        "low end" not in html.split("Reading")[0]
    )  # anchor prose 'low end' not leaked into legend


def test_players_grouped_when_sharing_side_and_tier() -> None:
    from schelling.report.render import render_forecast_narrative as rfn

    def actor(i: str, pos: float) -> Actor:
        return Actor(
            id=i,
            name=i.upper(),
            position=T(low=pos, mode=pos, high=pos),
            salience=T(low=90, mode=90, high=90),
            capability=T(low=50, mode=50, high=50),
        )

    game = _game(_BANDS).model_copy(
        update={"actors": [actor("a", 10), actor("b", 15), actor("c", 20)]}
    )
    rec = _record([10, 30, 60], median=30.0, bands=_BANDS).model_copy(update={"game": game})
    html = rfn(rec)
    # three actors share the low third + high salience tier -> one grouped sentence
    assert "Three members sit near the low end:" in html
    assert "a defining issue for each" in html
