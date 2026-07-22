"""The research dossier (Session 26): the hard wall between COMPUTED and NARRATIVE.

Tag resolution and its failure on an unresolved tag, numeral rejection in the narrative, computed-
section determinism, the fully-deterministic --no-narrative mode, advise-record integration, the
read-only guarantee (a record file is never modified), PDF build (gated), and section order.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.cli import app
from schelling.dossier.assemble import assemble_dossier, record_context
from schelling.dossier.narrative import (
    NarrativeRejectedError,
    build_tag_values,
    generate_narrative,
    invented_numerals,
    resolve_tags,
    validate_narrative,
)
from schelling.dossier.pdf import weasyprint_available
from schelling.formalizer.client import LLMResult, ReplayClient
from schelling.schemas.forecast import ForecastRecord

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def _record() -> ForecastRecord:
    data = json.loads((FIXTURES / "report" / "forecast_narrative.json").read_text())
    return ForecastRecord.model_validate(data)


_GOOD = (
    "[[history]] The file has been contested since 2025 (Wire, 2026-06-10).\n"
    "[[present_state]] Talks continue (Wire, 2026-07-01).\n"
    "[[interpretation]] The board tilts to {{modal_band}} at {{modal_share}}; median {{median}}.\n"
    "[[enforceability]] Commitments here are hard to verify; reversibility is high.\n"
    "[[limitations]] The model cannot see backroom deals."
)


# --------------------------------------------------------------- tag resolution (item 2)
def test_tag_resolution_and_unresolved_failure() -> None:
    values = {"median": "34", "ci80": "22 to 45"}
    resolved, unresolved = resolve_tags("median {{median}} over {{ci80}}", values)
    assert resolved == "median 34 over 22 to 45" and unresolved == []
    _, missing = resolve_tags("the {{bogus}} band", values)
    assert missing == ["bogus"]
    assert validate_narrative("the {{bogus}} band", values) == ["unresolved tag {{bogus}}"]


def test_build_tag_values_from_record() -> None:
    values = build_tag_values(_record())
    assert "median" in values and "modal_band" in values and "ci80" in values
    assert values["model"] in ("challenge", "compromise")


# --------------------------------------------------------------- numeral rejection (item 2)
def test_numeral_rejection() -> None:
    values = {"modal_share": "37%", "median": "34"}
    assert invented_numerals("a 37% chance") == ["37%"]
    assert invented_numerals("the median is 34") == ["median is 3"]
    assert invented_numerals("an 80% interval") == []  # the CI level is allowed verbatim
    assert invented_numerals("the {{modal_share}} of draws on 10 June 2026") == []  # tags/dates ok
    assert validate_narrative("a 37% chance", values)  # non-empty -> rejected


# --------------------------------------------------------------- narrative generation (item 2, 4)
def test_generate_narrative_retries_then_accepts() -> None:
    rec = _record()
    bad = _GOOD.replace("{{modal_share}}", "37%")  # invented numeral -> rejected on first attempt
    client = ReplayClient([LLMResult(bad, 1000, 500), LLMResult(_GOOD, 1000, 500)])
    n = generate_narrative(client, rec, situation_text="situation", sources_text="src")
    assert sorted(n.sections) == [
        "enforceability",
        "history",
        "interpretation",
        "limitations",
        "present_state",
    ]
    assert len(client.calls) == 2  # it retried once after the rejection
    assert len(n.sha256) == 64  # the narrative commits to its own SHA-256


def test_generate_narrative_rejects_when_all_attempts_fail() -> None:
    rec = _record()
    bad = _GOOD.replace("{{modal_share}}", "37%")
    client = ReplayClient([LLMResult(bad, 1, 1)] * 3)
    with pytest.raises(NarrativeRejectedError):
        generate_narrative(client, rec, situation_text="x", max_retries=2)


def test_narrative_firewall_rejects_a_concept_leak() -> None:
    rec = _record()
    # A distinctive concept phrase not present in the allowed text must not appear in the prose.
    leaky = _GOOD.replace("backroom deals", "loss domain risk seeking dominates the calculus here")
    client = ReplayClient([LLMResult(leaky, 1, 1)] * 3)
    with pytest.raises(NarrativeRejectedError):
        generate_narrative(
            client,
            rec,
            situation_text="a committee vote",
            concepts_text="loss domain risk seeking is a prospect-theory concept",
            max_retries=2,
        )


# --------------------------------------------------------------- assembly (items 3, 4)
_SECTION_ORDER = [
    "Executive verdict",
    "The question and the scale",
    "How we got here",
    "Present state",
    "The formal game",
    "The forecast",
    "Why this outcome",
    "Strategy by actor",
    "Enforceability and compliance",
    "Historical analogs",
    "What would change this",
    "Limitations and what this cannot see",
    "Provenance appendix",
]


def test_dossier_has_all_sections_in_order() -> None:
    html = assemble_dossier(_record(), narrative=None)
    # Match the numbered <h2> markers, not bare phrases (some, e.g. "what would change this", also
    # appear inside earlier sections).
    positions = [html.index(f"{i}.</span> {title}") for i, title in enumerate(_SECTION_ORDER, 1)]
    assert positions == sorted(positions)  # sections appear in the specified order
    assert "Band-probability strip" in html and "Weighted actor positions" in html  # figures inline


def test_no_narrative_mode_is_fully_deterministic() -> None:
    rec = _record()
    a = assemble_dossier(rec, narrative=None)
    b = assemble_dossier(rec, narrative=None)
    assert a == b  # byte-identical
    assert "Narrative omitted" in a  # the placeholder is shown
    assert "narrative sha256" not in a  # no narrative provenance without a narrative


def test_narrative_dossier_is_deterministic_for_fixed_sections() -> None:
    rec = _record()
    client = ReplayClient([LLMResult(_GOOD, 1000, 500)])
    n = generate_narrative(client, rec, situation_text="s")
    a = assemble_dossier(rec, narrative=n)
    b = assemble_dossier(rec, narrative=n)
    assert a == b  # same record + same narrative sections -> byte-identical
    assert "model-written and source-cited" in a  # the disclosure is stated
    assert n.sha256 in a and "narrative sha256" in a  # narrative provenance recorded
    # the interpretation's tags were resolved to computed values, not left raw
    assert "{{modal_band}}" not in a and "{{median}}" not in a


def test_computed_quantities_never_come_from_the_model() -> None:
    # A resolved tag equals the record's computed value, regardless of surrounding model prose.
    rec = _record()
    values = build_tag_values(rec)
    resolved, _ = resolve_tags("the median is {{median}}", values)
    assert resolved == f"the median is {rec.ensemble.median:.0f}"


def test_advise_records_fold_into_strategy_section() -> None:
    from schelling.schemas.forecast import AdviseRecord

    adv_path = next((Path("runs")).glob("*-advise-compromise-*.json"), None)
    if adv_path is None:
        pytest.skip("no advise record available locally (runs/ is gitignored)")
    adv = AdviseRecord.model_validate_json(adv_path.read_text())
    html = assemble_dossier(_record(), advise_records=[adv], narrative=None)
    assert f"Advising {adv.advising_actor}" in html


# --------------------------------------------------------------- CLI + read-only (items 1, 6)
def test_cli_dossier_no_narrative_and_never_modifies_the_record(tmp_path: Path) -> None:
    src = FIXTURES / "report" / "forecast_narrative.json"
    rec_path = tmp_path / "rec.json"
    shutil.copy(src, rec_path)
    before = rec_path.read_bytes()
    out = tmp_path / "out.html"
    result = runner.invoke(app, ["dossier", str(rec_path), "--no-narrative", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.read_text().count("Provenance appendix") == 1
    assert rec_path.read_bytes() == before  # the record file is never modified (item 6)


def test_cli_dossier_requires_api_key_or_no_narrative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force the no-key path deterministically: drop the var AND stop the startup .env reload, so the
    # guard fires without ever making a live API call (hermetic locally and on CI).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("schelling.cli.load_dotenv", lambda *a, **k: False)
    rec_path = tmp_path / "rec.json"
    shutil.copy(FIXTURES / "report" / "forecast_narrative.json", rec_path)
    result = runner.invoke(app, ["dossier", str(rec_path)])  # narrative on, no key
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output and "--no-narrative" in result.output


# --------------------------------------------------------------- PDF (item 5, gated)
@pytest.mark.skipif(not weasyprint_available(), reason="WeasyPrint (pdf extra) not installed")
def test_pdf_builds(tmp_path: Path) -> None:
    from schelling.dossier.pdf import html_to_pdf

    html = assemble_dossier(_record(), narrative=None)
    out = tmp_path / "d.pdf"
    html_to_pdf(html, out)
    assert out.read_bytes().startswith(b"%PDF")


def test_record_context_is_the_only_provenance() -> None:
    situation, _sources = record_context(_record())
    assert situation.startswith("QUESTION ")
    assert "CONTINUUM" in situation and "ACTORS AND EVIDENCE" in situation
