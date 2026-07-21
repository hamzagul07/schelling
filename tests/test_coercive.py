"""Coercive head-to-head harness tests (Session 11, items 1-2). Synthetic fixture only."""

from __future__ import annotations

from pathlib import Path

from schelling.backtest.coercive import head_to_head, load_library

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "coercive_sample.json"


def test_empty_library_reports_deferred() -> None:
    rep = head_to_head(load_library(FIXTURES / "does_not_exist.json"))
    assert rep.n_cases == 0
    assert "deferred" in rep.note and "paywalled" in rep.note


def test_head_to_head_scores_all_models_with_ci() -> None:
    cases = load_library(SAMPLE)  # synthetic 2-case fixture
    assert len(cases) == 2
    rep = head_to_head(cases)
    keys = {m.key for m in rep.methods}
    assert keys == {"challenge", "compromise", "gravity", "regime"}
    comp = next(m for m in rep.methods if m.key == "compromise")
    assert comp.delta_vs_compromise == 0.0  # compromise vs itself
    for m in rep.methods:
        assert m.ci_lo <= m.delta_vs_compromise <= m.ci_hi or m.key == "compromise"


def test_small_n_honesty_note() -> None:
    rep = head_to_head(load_library(SAMPLE))
    assert "tiny" in rep.note and "no verdict" in rep.note.lower()


# --------------------------------------------------------------- the registered KTAB library
KTAB = Path("data/coercive-cases/ktab-china-2014.json")


def test_ktab_library_loads_and_builds_valid_games() -> None:
    cases = load_library(KTAB)
    assert len(cases) == 2
    a, b = cases
    assert len(a.game.actors) == 26 and len(b.game.actors) == 34
    # rich schema adapted: continuum label, primary + secondary outcomes, metadata carried
    assert a.outcome == 25.0 and a.outcome_secondary == [55.0]
    assert a.ex_ante is True and a.verified is False  # draft-1, unverified
    assert "private participation" in a.continuum.lower()


def test_ktab_smoke_run_claims_no_verdict() -> None:
    rep = head_to_head(load_library(KTAB))
    assert rep.n_cases == 2
    assert {m.key for m in rep.methods} == {"challenge", "compromise", "gravity", "regime"}
    # all three guards fire: tiny N, unverified, out of the coercive domain
    assert "no verdict" in rep.note.lower()
    assert "UNVERIFIED" in rep.note and "coercive domain" in rep.note


def test_head_to_head_is_deterministic() -> None:
    cases = load_library(SAMPLE)
    a = head_to_head(cases, seed=1)
    b = head_to_head(cases, seed=1)
    assert [(m.key, m.mae, m.ci_lo, m.ci_hi) for m in a.methods] == [
        (m.key, m.mae, m.ci_lo, m.ci_hi) for m in b.methods
    ]
