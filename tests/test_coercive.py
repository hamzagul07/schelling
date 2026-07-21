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
    assert "small" in rep.note and "no verdict" in rep.note.lower()


def test_head_to_head_is_deterministic() -> None:
    cases = load_library(SAMPLE)
    a = head_to_head(cases, seed=1)
    b = head_to_head(cases, seed=1)
    assert [(m.key, m.mae, m.ci_lo, m.ci_hi) for m in a.methods] == [
        (m.key, m.mae, m.ci_lo, m.ci_hi) for m in b.methods
    ]
