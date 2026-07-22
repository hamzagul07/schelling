"""The precedent layer / outside view (Session 29): no auto-acceptance, ratification gating, panel
separation, divergence, determinism, sealed records untouched.

The finder is replayed (ReplayClient) so CI never calls the live API.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import _precedent_evidence, _ratified_precedent_panel, app
from schelling.formalizer.client import LLMResult, ReplayClient
from schelling.precedents.find import PrecedentSearchError, find_precedents, parse_precedents
from schelling.precedents.panel import (
    build_precedent_panel,
    divergence,
    divergence_line,
    is_ratified,
)
from schelling.precedents.schemas import PrecedentSet
from schelling.report.render import render
from schelling.schemas.forecast import ForecastRecord
from schelling.schemas.question import GameSpec

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"

# Two ex-ante precedents both land in the low "Censure and referral" band (0-24) so the base rate is
# a single, unambiguous band; the third is hindsight-coded (excluded from the base rate).
_ARR = (
    '[{"id":"p1","what_happened":"Board censured Iran","date":"2024-11","source":"Reuters 2024",'
    '"proposed_placement":10,"reasoning":"same body, firm","ex_ante_codable":true},'
    '{"id":"p2","what_happened":"Board referred Iran","date":"2025-06","source":"IAEA 2025",'
    '"proposed_placement":15,"reasoning":"same body, firm again","ex_ante_codable":true},'
    '{"id":"p3","what_happened":"post-hoc coded","date":"2020","source":"X","proposed_placement":8,'
    '"reasoning":"h","ex_ante_codable":false}]'
)


def _game() -> GameSpec:
    return GameSpec.model_validate(
        json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())["game"]
    )


def _pset() -> PrecedentSet:
    return find_precedents(ReplayClient([LLMResult(_ARR, 100, 50)]), _game())


def _ratify(pset: PrecedentSet) -> PrecedentSet:
    return pset.model_copy(
        update={
            "ratification_note": "Ratified by Hassan 2026-07-23",
            "precedents": [p.model_copy(update={"ratified": True}) for p in pset.precedents],
        }
    )


def _record_with_panel(median: float) -> ForecastRecord:
    d = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    d["ensemble"]["median"] = median
    panel = build_precedent_panel(_ratify(_pset()), _game())
    d["precedent_panel"] = panel.model_dump()
    return ForecastRecord.model_validate(d)


# --------------------------------------------------------------- no auto-acceptance (items 1, 2)
def test_finder_proposes_nothing_is_accepted() -> None:
    pset = _pset()
    assert len(pset.precedents) == 3
    assert all(not p.ratified for p in pset.precedents)  # every placement is a PROPOSAL
    assert pset.ratification_note == ""
    assert not is_ratified(pset)


def test_parse_rejects_and_skips_malformed() -> None:
    with pytest.raises(PrecedentSearchError):
        parse_precedents("no array here")
    # a malformed entry is skipped, valid ones kept
    good = parse_precedents(
        '[{"bad":1},{"id":"x","what_happened":"w","date":"2024","source":"s",'
        '"proposed_placement":40,"reasoning":"r","ex_ante_codable":true}]'
    )
    assert len(good) == 1 and good[0].id == "x"


# --------------------------------------------------------------- ratification gating (item 2)
def test_ratification_required_before_panel() -> None:
    assert not is_ratified(_pset())
    assert is_ratified(_ratify(_pset()))
    # only ratified, ex-ante precedents form the base rate; hindsight carried separately
    panel = build_precedent_panel(_ratify(_pset()), _game())
    assert len(panel.precedents) == 2 and len(panel.hindsight_precedents) == 1
    assert panel.hindsight_precedents[0].ex_ante_codable is False


def test_helper_refuses_unratified(tmp_path: Path) -> None:
    p = tmp_path / "unrat.json"
    p.write_text(_pset().model_dump_json())
    with pytest.raises(ValueError, match="not ratified"):
        _ratified_precedent_panel(p, _game())


# --------------------------------------------------------------- panel separation (item 3)
def test_panel_is_disclosed_and_never_blended() -> None:
    panel = build_precedent_panel(_ratify(_pset()), _game())
    assert panel.blend_weight == 0.0
    html = render(json.loads(_record_with_panel(61.0).model_dump_json()))
    assert "Reference class — the outside view" in html
    assert "never blended" in html
    assert "hindsight-coded" in html and "Reported separately" in html
    assert "Ratified by Hassan 2026-07-23" in html  # ratification quoted


# --------------------------------------------------------------- divergence (item 5)
def test_divergence_fires_only_across_bands() -> None:
    # model median 61 -> "No new action" band; precedents concentrate low -> divergence
    diverge = _record_with_panel(61.0)
    assert divergence(diverge) is not None
    assert divergence_line(diverge).startswith("OUTSIDE VIEW DISAGREES")
    # model median 20 -> same band as the precedent base rate -> no divergence
    agree = _record_with_panel(20.0)
    assert divergence(agree) is None and divergence_line(agree) == ""


# --------------------------------------------------------------- determinism
def test_panel_and_render_are_deterministic() -> None:
    a = build_precedent_panel(_ratify(_pset()), _game())
    b = build_precedent_panel(_ratify(_pset()), _game())
    assert a == b
    data = json.loads(_record_with_panel(61.0).model_dump_json())
    assert render(data) == render(data)


# --------------------------------------------------------------- evidence river (item 4)
def test_precedent_evidence_is_ratification_gated(tmp_path: Path) -> None:
    rat = tmp_path / "rat.json"
    rat.write_text(_ratify(_pset()).model_dump_json())
    evidence = _precedent_evidence(rat)
    assert len(evidence) == 3 and any("Board censured Iran" in v for v in evidence.values())
    unrat = tmp_path / "unrat.json"
    unrat.write_text(_pset().model_dump_json())
    with pytest.raises(ValueError, match="not ratified"):
        _precedent_evidence(unrat)


# --------------------------------------------------------------- CLI + sealed records untouched
def test_cli_precedents_writes_unratified_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_path = tmp_path / "game.json"
    game_path.write_text(_game().model_dump_json())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(
        "schelling.cli.AnthropicClient", lambda model="m": ReplayClient([LLMResult(_ARR, 100, 50)])
    )
    result = runner.invoke(app, ["precedents", str(game_path), "-o", str(tmp_path / "p.json")])
    assert result.exit_code == 0, result.output
    assert "ALL unratified" in result.output
    written = PrecedentSet.model_validate_json((tmp_path / "p.json").read_text())
    assert all(not p.ratified for p in written.precedents)  # nothing accepted (item 1)


def test_cli_solve_precedents_attaches_and_diverges(tmp_path: Path) -> None:
    game_path = tmp_path / "game.json"
    game_path.write_text(_game().model_dump_json())
    prec = tmp_path / "prec.json"
    prec.write_text(_ratify(_pset()).model_dump_json())
    result = runner.invoke(
        app,
        [
            "solve",
            str(game_path),
            "--solver",
            "compromise",
            "--draws",
            "200",
            "--precedents",
            str(prec),
            "--out-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "OUTSIDE VIEW DISAGREES" in result.output  # divergence printed in solve output (item 5)
    rec = next(tmp_path.glob("*-compromise-*.json"))
    assert ForecastRecord.model_validate_json(rec.read_text()).precedent_panel is not None


def test_dossier_precedents_never_modifies_the_record(tmp_path: Path) -> None:
    rec_path = tmp_path / "rec.json"
    shutil.copy(FIXTURES / "report" / "forecast_narrative.json", rec_path)
    before = rec_path.read_bytes()
    prec = tmp_path / "prec.json"
    prec.write_text(_ratify(_pset()).model_dump_json())
    out = tmp_path / "d.html"
    result = runner.invoke(
        app,
        ["dossier", str(rec_path), "--no-narrative", "--precedents", str(prec), "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert "Reference class — the outside view" in out.read_text()
    assert rec_path.read_bytes() == before  # the record file is never modified
