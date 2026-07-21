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
    assert a.ex_ante is True and a.verified is True  # D13.0: numbers verified + judgments ratified
    assert "private participation" in a.continuum.lower()


def test_ktab_smoke_run_claims_no_verdict() -> None:
    rep = head_to_head(load_library(KTAB))
    assert rep.n_cases == 2
    assert {m.key for m in rep.methods} == {"challenge", "compromise", "gravity", "regime"}
    # two guards still fire: tiny N + out of the coercive domain (transcription now verified, D13.0)
    assert "no verdict" in rep.note.lower()
    assert "tiny" in rep.note and "coercive domain" in rep.note
    assert "UNVERIFIED" not in rep.note  # numbers exact + judgments ratified


def test_head_to_head_is_deterministic() -> None:
    cases = load_library(SAMPLE)
    a = head_to_head(cases, seed=1)
    b = head_to_head(cases, seed=1)
    assert [(m.key, m.mae, m.ci_lo, m.ci_hi) for m in a.methods] == [
        (m.key, m.mae, m.ci_lo, m.ci_hi) for m in b.methods
    ]


# --------------------------------------------------------------- model-three integration (Session 20)
import json  # noqa: E402

import pytest  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from schelling.cli import app  # noqa: E402

_runner = CliRunner()


def _coded_case_file(tmp_path: Path) -> Path:
    lib = tmp_path / "syn.json"
    lib.write_text(
        json.dumps(
            {
                "transcription": {"verified": True},
                "cases": [
                    {
                        "case_id": "SYN-1",
                        "title": "t",
                        "domain": "coercive_interstate",
                        "ex_ante": True,
                        "source": "synthetic",
                        "reference_point": 50,
                        "continuum": {"label": "x", "anchor_0": "a", "anchor_100": "b"},
                        "actors": [
                            {
                                "id": "s",
                                "name": "S",
                                "position": 20,
                                "salience": 60,
                                "capability": 90,
                            },
                            {
                                "id": "w",
                                "name": "W",
                                "position": 80,
                                "salience": 60,
                                "capability": 40,
                            },
                        ],
                        "outcomes": {"o": {"proposed_value": 45, "primary": True}},
                        "coding_flags": {
                            "case": {
                                "horizon_months": {"value": 24, "citation": "c"},
                                "vulnerability": {"value": 1, "citation": "c"},
                                "guarantor": {"value": 0, "citation": "c"},
                            },
                            "actors": {
                                "s": {
                                    "cohesion": {"value": "exceptional", "citation": "c"},
                                    "endurance": {"value": "comfortable", "citation": "c"},
                                    "loss": {"value": 1, "citation": "c"},
                                    "perception": {"value": "ledger", "citation": "c"},
                                },
                                "w": {
                                    "cohesion": {"value": "fractured", "citation": "c"},
                                    "endurance": {"value": "hardened", "citation": "c"},
                                    "perception": {"value": "lens", "citation": "c"},
                                },
                            },
                        },
                    }
                ],
            }
        )
    )
    return lib


def test_coding_flags_loaded_and_model_three_scores_via_harness(tmp_path: Path) -> None:
    from schelling.backtest.coercive import _METHODS, MODEL_THREE, _forecast, head_to_head
    from schelling.backtest.model_three import model_three_forecast

    cases = load_library(_coded_case_file(tmp_path))
    coding = cases[0].coding
    assert coding is not None and len(coding.mt_actors) == 2 and coding.horizon_months == 24
    expected = model_three_forecast(
        coding.mt_actors,
        reference_point=50.0,
        horizon_months=24,
        vulnerability=True,
        guarantor=False,
    )
    assert _forecast(MODEL_THREE, cases[0]) == expected
    rep = head_to_head(cases, methods=(*_METHODS, MODEL_THREE))
    assert any(m.key == MODEL_THREE for m in rep.methods)


def test_model_three_refuses_a_case_without_coding_flags() -> None:
    from schelling.backtest.coercive import MODEL_THREE, _forecast

    china = load_library(Path("data/coercive-cases/ktab-china-2014.json"))
    with pytest.raises(ValueError, match="no coding_flags"):
        _forecast(MODEL_THREE, china[0])


def test_cli_coercive_refuses_model_three_before_the_reading() -> None:
    # The real library is not the reading: model-three must refuse (never run before 8 verified cases).
    result = _runner.invoke(app, ["coercive", "--solver", "model-three"])
    assert result.exit_code == 2
    assert (
        "Refusing to run model-three" in result.output
        and "reading has not arrived" in result.output
    )
