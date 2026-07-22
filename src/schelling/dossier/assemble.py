"""Assemble the research dossier from a forecast record + advise records + narrative (Session 26).

The HARD WALL: COMPUTED sections are deterministic template text from the existing renderer; the
five NARRATIVE sections are model-written, tag-resolved, and clearly labelled. ``--no-narrative``
(``narrative=None``) yields a fully deterministic dossier. Section order follows D26.3.
"""

from __future__ import annotations

from schelling.dossier.narrative import NarrativeSections, build_tag_values, resolve_tags
from schelling.report import svg
from schelling.report.bands import compromise_point, map_bands
from schelling.report.render import (
    _NARR_CSS,
    _actor_table,
    _analog_panel,
    _dl,
    _esc,
    _narr_assumptions_split,
    _narr_diagnostics,
    _narr_solvers,
    _narr_verdict,
    _page,
    _reading_diagram,
    _sensitivity_warning,
    _short_name,
    _sources_list,
    _strategy_sections,
    _targets_table,
    _tornado,
    _verdict_strip,
    _what_would_change,
)
from schelling.report.vocab import load_vocab, phrase_for
from schelling.schemas.forecast import AdviseRecord, ForecastRecord

_DOSSIER_CSS = """
.dossier h2 { font-size:15px; color:var(--ink); border-bottom:2px solid var(--line);
  padding-bottom:4px; margin:34px 0 12px; text-transform:none; letter-spacing:0; }
.dossier .secnum { color:var(--muted); font-weight:400; }
.narrative-note { border-left:3px solid var(--accent); background:#fff7ed; color:#7c2d12;
  padding:8px 12px; font-size:12px; margin:8px 0 12px; border-radius:0 6px 6px 0; }
.model-written p { margin:8px 0; }
.model-written { font-size:14.5px; line-height:1.6; }
/* PDF pagination (D26.5): page numbers + a running header with question id and freeze date. The
   .runhead element is positioned off-screen (not display:none, so string-set still fires). */
.runhead { position:absolute; left:-9999px; top:0; string-set:runhead content(); }
@page { size:A4; margin:20mm 16mm;
  @top-left { content:string(runhead); font-size:9px; color:#6b7280; }
  @bottom-right { content:"Page " counter(page) " of " counter(pages); font-size:9px;
    color:#6b7280; } }
@media print { .dossier h2 { break-after:avoid; } figure, table { break-inside:avoid; } }
"""


def record_context(record: ForecastRecord) -> tuple[str, str]:
    """Derive the narrative's inputs from the record: a situation summary + the fetched-source text.

    The record is self-contained (continuum, notes, actor evidence, assumptions, sources), so the
    dossier needs no separate situation file. This is the ONLY provenance the narrative may cite.
    """
    game = record.game
    assert game is not None
    c = game.continuum
    lines = [
        f"QUESTION {record.question_id}",
        f"CONTINUUM: {c.label}. 0 = {c.anchor_0}. 100 = {c.anchor_100}.",
        f"HORIZON: {game.horizon}.",
    ]
    if game.notes:
        lines.append(f"NOTES: {game.notes}")
    lines.append("ACTORS AND EVIDENCE:")
    for a in game.actors:
        lines.append(f"- {a.name} (id {a.id})")
        for ev in a.evidence:
            lines.append(f"    * {ev.note} — {ev.source}, {ev.date}")
    if record.assumptions:
        lines.append("ASSUMPTIONS (asserted where sources were silent):")
        lines += [f"- {asm.statement} (why: {asm.why})" for asm in record.assumptions]
    situation = "\n".join(lines)
    sources = "\n".join(
        f"- {s.title or s.url} ({s.url}){': ' + s.snippet if s.snippet else ''}"
        for s in record.sources_fetched
    )
    return situation, sources


_NARRATIVE_DISCLOSURE = (
    "The italicised sections below (history, present state, interpretation, enforceability, "
    "limitations) are model-written and source-cited. Every number in this dossier is computed "
    "by the deterministic solver — the narrative states model quantities only through resolved "
    "tags, never invented figures."
)


def _h2(num: int, title: str) -> str:
    return f'<h2><span class="secnum">{num}.</span> {_esc(title)}</h2>'


def _prose_html(text: str) -> str:
    """Model prose -> escaped paragraphs (blank-line separated)."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{_esc(p)}</p>" for p in paras) or "<p></p>"


def _narrative_section(
    num: int,
    title: str,
    slot: str,
    narrative: NarrativeSections | None,
    values: dict[str, str],
) -> str:
    """A model-written section (resolved tags), or a deterministic placeholder in --no-narrative."""
    head = _h2(num, title)
    if narrative is None:
        return (
            f"{head}<p class='sub'><em>Narrative omitted (--no-narrative): this dossier is fully "
            f"deterministic. Re-run without the flag to add model-written, source-cited prose.</em>"
            f"</p>"
        )
    resolved, _ = resolve_tags(narrative.sections.get(slot, ""), values)
    return f"{head}<div class='model-written'>{_prose_html(resolved)}</div>"


def _question_and_scale(record: ForecastRecord) -> str:
    game = record.game
    assert game is not None
    c = game.continuum
    return (
        f"<p>The question is scored on a 0&ndash;100 continuum: <strong>{_esc(c.label)}</strong>. "
        f"<strong>0</strong> means {_esc(c.anchor_0)}; <strong>100</strong> means "
        f"{_esc(c.anchor_100)}. Horizon: {_esc(game.horizon)}.</p>"
    )


def _why_this_outcome_computed(record: ForecastRecord) -> str:
    """The deterministic weight arithmetic that sits under the model-written interpretation."""
    game = record.game
    assert game is not None
    v = load_vocab()
    weights = [(a, a.capability.mode * a.salience.mode) for a in game.actors]
    total = sum(w for _, w in weights) or 1.0
    heaviest = sorted(weights, key=lambda x: (-x[1], x[0].id))[:3]
    desc = ", ".join(f"{_esc(_short_name(game, a))} ({w / total:.0%})" for a, w in heaviest)
    cp = compromise_point(game)
    return (
        f"<p class='sub'>Computed basis: the settlement is a capability&times;salience weighted "
        f"average of actor positions. The heaviest weights sit with {desc}, pulling the result "
        f"{_esc(phrase_for(heaviest[0][0].position.mode, v.position_thirds))}; the closed-form "
        f"weighted mean is {cp:.0f}.</p>"
    )


def _strategy_by_actor(advise_records: list[AdviseRecord]) -> str:
    """Own moves, net-after-response, robustness, persuasion targets, packages, equilibrium."""
    if not advise_records:
        return "<p class='sub'>No advise records were supplied for this dossier.</p>"
    parts: list[str] = []
    for adv in advise_records:
        lens = "exact weighted-mean" if adv.exact else "simulated challenge"
        parts.append(
            f"<h3>Advising {_esc(adv.advising_actor)} "
            f"<span class='ev'>(ideal {adv.ideal:g} · {lens} lens · baseline "
            f"{adv.baseline_median:.1f})</span></h3>"
        )
        if adv.top_moves:
            parts.append("<h4>Top own moves</h4>")
            from schelling.report.render import _own_moves_table

            parts.append(_own_moves_table(adv.top_moves))
        if adv.persuasion_targets:
            parts.append("<h4>Persuasion targets</h4>")
            parts.append(_targets_table(adv.persuasion_targets))
        parts.append(_strategy_sections(adv))  # response/robustness, packages, equilibrium, brief
    return "".join(parts)


def _provenance_appendix(
    record: ForecastRecord,
    narrative: NarrativeSections | None,
    rubric_source: str | None,
) -> str:
    game = record.game
    rubric = game.resolution_rubric if game is not None else None
    src = "none (no rubric)" if rubric is None else (rubric_source or "embedded in the record")
    pairs = {
        "question": record.question_id,
        "run id": record.run_id,
        "inputs_hash": record.inputs_hash,
        "engine (git SHA)": record.engine_version,
        "seed": str(record.seed),
        "model": record.model,
        "n_draws": str(record.ensemble.n_draws),
        "rubric source": src,
        "reproduce": (
            f"schelling solve <game>.json --seed {record.seed} "
            f"--solver {record.model} --draws {record.ensemble.n_draws}"
        ),
    }
    if narrative is not None:
        pairs["narrative model"] = narrative.model
        pairs["narrative cost"] = f"${narrative.cost_usd:.4f}"
        pairs["narrative sha256"] = narrative.sha256
        pairs["narrative note"] = "model-written; re-running produces different prose"
    else:
        pairs["narrative"] = "omitted (--no-narrative); fully deterministic dossier"
    body = _dl(pairs)
    sources = ""
    if record.sources_fetched:
        sources = f"<h3>Sources fetched ({len(record.sources_fetched)})</h3>" + _sources_list(
            record.sources_fetched
        )
    return f'<div class="prov">Provenance{body}</div>{sources}'


def assemble_dossier(
    record: ForecastRecord,
    *,
    advise_records: list[AdviseRecord] | None = None,
    narrative: NarrativeSections | None = None,
    rubric_source: str | None = None,
) -> str:
    """Assemble the full dossier HTML. ``narrative=None`` yields a fully deterministic document."""
    game = record.game
    if game is None:
        raise ValueError("a dossier needs a record with an embedded game")
    advise = advise_records or []
    readout = map_bands(record)
    values = build_tag_values(record)
    e = record.ensemble

    parts: list[str] = [
        f'<div class="runhead">{_esc(record.question_id)} · frozen {_esc(game.frozen_at)}</div>',
        f'<div class="kicker">Research dossier</div><h1>{_esc(record.question_id)}</h1>',
        f'<p class="sub">frozen {_esc(game.frozen_at)} · {_esc(record.model)} model · '
        f"run {_esc(record.run_id)}</p>",
        f"<div class='narrative-note'>{_esc(_NARRATIVE_DISCLOSURE)}</div>"
        if narrative is not None
        else "",
        # 1. Executive verdict (COMPUTED)
        _h2(1, "Executive verdict"),
        _narr_verdict(record, game, readout),
        # 2. The question and the scale (COMPUTED)
        _h2(2, "The question and the scale"),
        _question_and_scale(record),
        # 3-4. History + present state (NARRATIVE)
        _narrative_section(3, "How we got here", "history", narrative, values),
        _narrative_section(4, "Present state", "present_state", narrative, values),
        # 5. The formal game (COMPUTED)
        _h2(5, "The formal game"),
        "<figure>" + _reading_diagram(record, game) + "</figure>",
        _actor_table(game, with_evidence=True),
        _narr_assumptions_split(record, game),
        # 6. The forecast (COMPUTED)
        _h2(6, "The forecast"),
        _verdict_strip(record, readout),
        "<h3>Outcome distribution</h3><figure>"
        + svg.histogram(record.outcome_distribution, p10=e.p10, p90=e.p90, median=e.median)
        + "</figure>",
        _narr_solvers(record, game, readout),
        _narr_diagnostics(record),
        # 7. Why this outcome (NARRATIVE + a computed basis line)
        _narrative_section(7, "Why this outcome", "interpretation", narrative, values),
        _why_this_outcome_computed(record),
        # 8. Strategy by actor (COMPUTED, from advise records)
        _h2(8, "Strategy by actor"),
        _strategy_by_actor(advise),
        # 9. Enforceability and compliance (NARRATIVE; analysis only)
        _narrative_section(9, "Enforceability and compliance", "enforceability", narrative, values),
        "<p class='sub'><em>This section is an analysis of how durable the resulting agreement is "
        "likely to be — an analysis of coalition durability, not a prescription.</em></p>",
    ]
    # 10. Historical analogs (COMPUTED, when present)
    parts.append(_h2(10, "Historical analogs"))
    if record.analog_panel is not None:
        parts.append(_analog_panel(record.analog_panel))
    else:
        parts.append("<p class='sub'>No analog panel is attached to this record.</p>")
    # 11. What would change this (COMPUTED)
    parts += [
        _h2(11, "What would change this"),
        _what_would_change(record, game),
        _sensitivity_warning(record),
        f"<figure>{_tornado(record)}</figure>" if record.sensitivity else "",
    ]
    # 12. Limitations (NARRATIVE)
    parts.append(
        _narrative_section(
            12, "Limitations and what this cannot see", "limitations", narrative, values
        )
    )
    # 13. Provenance appendix (COMPUTED)
    parts += [
        _h2(13, "Provenance appendix"),
        _provenance_appendix(record, narrative, rubric_source),
    ]

    body = f'<div class="dossier">{"".join(parts)}</div>'
    return _page(f"Dossier — {record.question_id}", body, extra_css=_NARR_CSS + _DOSSIER_CSS)
