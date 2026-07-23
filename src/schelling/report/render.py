"""Render Schelling artifacts to a single self-contained HTML report.

Accepts a ``DraftGameSpec`` (review sheet) or a ``ForecastRecord`` (full analysis). Output is
one HTML file with all CSS inlined, charts as inline SVG (no JS, no network), deterministic for
a given artifact (no wall-clock — CLAUDE.md rule 2). Opens offline and prints cleanly.
"""

from __future__ import annotations

import html
import re
from typing import Any

from pydantic import ValidationError

from schelling.backtest.context import CITATIONS, CONTEXT_PROSE, PUBLISHED_RESULTS
from schelling.formalizer.schemas import DraftGameSpec, FetchedSource
from schelling.mc.sensitivity import zero_swing_warning
from schelling.report import svg
from schelling.report.bands import (
    BANDED,
    BandReadout,
    band_containing,
    compromise_point,
    map_bands,
)
from schelling.report.palette import load_palette
from schelling.report.svg import (
    ActorPoint,
    BandSeg,
    BarRow,
    ScatterPoint,
    TornadoRow,
    WActor,
    format_share,
)
from schelling.report.vocab import load_vocab, phrase_for
from schelling.schemas.backtest import BacktestRecord
from schelling.schemas.forecast import (
    ADVISE_CAVEAT,
    SUCCESSOR_CAVEAT,
    AdviseRecord,
    AnalogPanel,
    Assumption,
    ForecastRecord,
    LLMForecastRecord,
    OwnMove,
    PersuasionTarget,
)
from schelling.schemas.question import GameSpec, RubricBand
from schelling.schemas.stakeholders import Actor

# Standing scope note shown beneath every verdict (D25.2): what the shares do and do not include.
_SHARE_SCOPE = (
    "These shares reflect uncertainty in the stated input ranges only. They exclude model error, "
    "coding error, and events outside the modelled game."
)

_CSS = """
:root { --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --panel:#f9fafb; --accent:#b45309; }
* { box-sizing:border-box; }
body { margin:0; color:var(--ink); background:#fff;
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:760px; margin:0 auto; padding:40px 28px 72px; }
h1 { font-size:22px; font-weight:650; margin:0 0 2px; letter-spacing:-.01em; }
h2 { font-size:13px; font-weight:650; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); margin:38px 0 12px; }
.sub { color:var(--muted); font-size:13px; margin:0 0 4px; }
.kicker { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
figure { margin:0; }
.metrics { display:flex; flex-wrap:wrap; gap:12px; margin:6px 0 4px; }
.metric { flex:1 1 130px; border:1px solid var(--line); border-radius:8px; padding:12px 14px;
  background:var(--panel); }
.metric .m-val { font-size:20px; font-weight:650; letter-spacing:-.01em; }
.metric .m-lab { color:var(--muted); font-size:11px; text-transform:uppercase;
  letter-spacing:.05em; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { text-align:left; padding:7px 8px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase;
  letter-spacing:.04em; }
td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
.ev { color:var(--muted); font-size:12px; }
.ev q { color:var(--ink); }
ul.checklist { list-style:none; margin:0; padding:0; }
ul.checklist li { border:1px solid var(--line); border-radius:8px; padding:10px 12px 10px 34px;
  position:relative; margin-bottom:8px; background:var(--panel); }
ul.checklist .box { position:absolute; left:11px; top:11px; width:14px; height:14px;
  border:1.5px solid #9ca3af; border-radius:3px; }
ul.checklist .why { color:var(--muted); font-size:12px; margin-top:3px; }
.prov { border-top:1px solid var(--line); margin-top:40px; padding-top:14px; color:var(--muted);
  font-size:12px; }
.prov dl { display:grid; grid-template-columns:150px 1fr; gap:3px 14px; margin:0; }
.prov dt { color:#9ca3af; }
.prov dd { margin:0; word-break:break-all; font-variant-numeric:tabular-nums; }
/* SVG chart classes */
.axis, .whisker, .baseline, .settle-line, .median-line { stroke:#9ca3af; fill:none; }
.axis { stroke:var(--line); } .whisker { stroke:#94a3b8; stroke-width:1.4; }
.dot { fill:#334155; } .bar { fill:#cbd5e1; } .tbar { fill:#94a3b8; }
.ci-band { fill:#eef2f7; } .traj-line { stroke:#334155; stroke-width:1.6; fill:none; }
.baseline { stroke-dasharray:3 3; } .settle-line, .median-line { stroke:var(--accent);
  stroke-width:1.4; stroke-dasharray:4 3; }
.tick, .actor-label, .swing, .settle-label { font:11px sans-serif; fill:var(--muted); }
.actor-label { fill:var(--ink); } .swing { fill:#374151; font-variant-numeric:tabular-nums; }
.settle-label { fill:var(--accent); font-weight:600; }
.caveat { border-left:3px solid var(--accent); background:#fff7ed; color:#7c2d12;
  padding:11px 14px; font-size:13px; margin:14px 0; border-radius:0 6px 6px 0; }
.flag { color:var(--accent); font-size:11px; }
.verdict { padding:12px 16px; border-radius:8px; font-weight:600; margin:8px 0 18px; }
.verdict.pass { background:#ecfdf5; color:#065f46; border:1px solid #6ee7b7; }
.verdict.fail { background:#fef2f2; color:#991b1b; border:1px solid #fca5a5; }
.cite { color:var(--muted); font-size:12px; }
tr.primary td { background:#fff7ed; }
.badge { display:inline-block; border:1px solid var(--accent); color:var(--accent);
  border-radius:10px; padding:0 7px; font-size:11px; letter-spacing:.03em; }
ul.sources { list-style:none; margin:0; padding:0; }
ul.sources li { border:1px solid var(--line); border-radius:8px; padding:9px 12px;
  margin-bottom:8px; background:var(--panel); }
ul.sources a { color:var(--accent); text-decoration:none; word-break:break-all; }
ul.sources .meta { color:var(--muted); font-size:12px; margin-top:2px; }
ul.sources .snip { color:var(--ink); font-size:12px; margin-top:4px; }
@media print { body { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  .wrap { max-width:none; padding:0 12px; } h2 { margin-top:24px; } }
"""

# Extra styles injected ONLY by the two-audience narrative report (D22.2), so every other report's
# stylesheet — and thus its golden — stays byte-identical.
_NARR_CSS = """
section.narr { margin:0 0 10px; }
.narr .lede { font-size:17px; line-height:1.5; margin:10px 0 12px; }
.narr h3 { font-size:12px; font-weight:650; text-transform:uppercase; letter-spacing:.05em;
  color:var(--muted); margin:22px 0 8px; }
.narr ul { margin:6px 0; padding-left:20px; } .narr li { margin:3px 0; }
.narr dl { display:grid; grid-template-columns:170px 1fr; gap:3px 14px; margin:6px 0;
  font-size:13px; }
.narr dt { color:#9ca3af; } .narr dd { margin:0; }
.narr pre { background:var(--panel); border:1px solid var(--line); border-radius:6px;
  padding:10px 12px; font-size:12px; overflow-x:auto; margin:6px 0; }
tr.modal td { background:#fff7ed; }
.narr figure { margin:10px 0 4px; }
.narr .legend { color:var(--muted); font-size:12px; margin:2px 0 6px; }
.narr .scope { color:var(--muted); font-size:12px; font-style:italic; margin:2px 0 10px; }
.band-pct { fill:#1f2937; font-size:11px; font-weight:650; }
.band-lab { fill:#6b7280; font-size:10px; }
.actor-dot-label { fill:#1f2937; font-size:10px; }
"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _rng(est: Any) -> str:
    return f"{est.low:g} / {est.mode:g} / {est.high:g}"


def _derive_short(name: str) -> str:
    """First clause of a name: text before the first parenthesis or spaced/en/em dash (D25.3)."""
    head = re.split("\\s*[(\u2013\u2014]", name, maxsplit=1)[0]  # cut at "(", en/em dash
    head = re.split(r"\s-\s", head, maxsplit=1)[0]  # cut at a spaced hyphen " - "
    return head.strip() or name


def _short_name(game: GameSpec, actor: Actor) -> str:
    """The actor's short display name: a ``short_names`` override, else the derived first clause."""
    return game.short_names.get(actor.id) or _derive_short(actor.name)


def _actor_points(game: GameSpec) -> list[ActorPoint]:
    return [
        ActorPoint(
            name=a.name,
            low=a.position.low,
            mode=a.position.mode,
            high=a.position.high,
            weight=a.capability.mode * a.salience.mode,
        )
        for a in game.actors
    ]


def _actor_table(game: GameSpec, *, with_evidence: bool) -> str:
    rows = []
    for a in game.actors:
        ev = ""
        if with_evidence:
            items = "".join(
                f'<div class="ev"><q>{_esc(e.note)}</q> — {_esc(e.source)}, {_esc(e.date)}</div>'
                for e in a.evidence
            )
            ev = items or '<div class="ev">(none supplied)</div>'
        cells = (
            f"<td>{_esc(a.name)}<br><span class='ev'>{_esc(a.id)}</span></td>"
            f"<td class='num'>{_rng(a.position)}</td>"
            f"<td class='num'>{_rng(a.salience)}</td>"
            f"<td class='num'>{_rng(a.capability)}</td>"
        )
        if with_evidence:
            cells += f"<td>{ev}</td>"
        rows.append(f"<tr>{cells}</tr>")
    ev_head = "<th>evidence</th>" if with_evidence else ""
    return (
        "<table><thead><tr><th>actor</th><th>position</th><th>salience</th>"
        f"<th>capability</th>{ev_head}</tr>"
        "<tr><th></th><th>low / mode / high</th><th>low / mode / high</th>"
        "<th>low / mode / high</th>" + ("<th></th>" if with_evidence else "") + "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _page(title: str, body: str, extra_css: str = "") -> str:
    # extra_css defaults to "" so every existing caller renders byte-identically; only the
    # narrative report passes _NARR_CSS (D22.5).
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title><style>{_CSS}{extra_css}</style></head>"
        f'<body><div class="wrap">{body}</div></body></html>\n'
    )


def render_draft(draft: DraftGameSpec) -> str:
    """Render a DraftGameSpec review sheet."""
    g = draft.game
    tc = draft.template_classification
    searched = (
        ' &nbsp;·&nbsp; <span class="badge">live-searched</span>' if draft.live_searched else ""
    )
    parts = [
        '<div class="kicker">Draft game specification — for review</div>',
        f"<h1>{_esc(g.question_id)}</h1>",
        f'<p class="sub">frozen {_esc(g.frozen_at)} · template: {_esc(tc.template)} · '
        f"horizon: {_esc(g.horizon)}{searched}</p>",
        f'<p class="sub"><strong>{_esc(g.continuum.label)}</strong><br>'
        f"0 = {_esc(g.continuum.anchor_0)} &nbsp;·&nbsp; 100 = {_esc(g.continuum.anchor_100)}</p>",
        "<h2>Actor map</h2>",
        f"<figure>{svg.actor_map(_actor_points(g))}</figure>",
        "<h2>Stakeholders</h2>",
        _actor_table(g, with_evidence=True),
        "<h2>Open assumptions — review before solving</h2>",
        _assumptions(draft),
    ]
    if draft.sources_fetched:
        parts += [
            "<h2>Sources fetched — live web search</h2>",
            _sources_list(draft.sources_fetched),
        ]
    m = draft.metadata
    prov = _dl(
        {
            "model": m.model,
            "tokens": f"in {m.input_tokens} · out {m.output_tokens}",
            "cost": f"${m.cost_usd:.4f}",
            "retries": str(m.retries),
        }
    )
    parts.append(f'<div class="prov">Provenance{prov}</div>')
    return _page(g.question_id, "".join(parts))


def _assumptions_html(items: list[Assumption]) -> str:
    if not items:
        return "<p class='sub'>(none)</p>"
    li = "".join(
        f'<li><span class="box"></span>{_esc(a.statement)}<div class="why">{_esc(a.why)}</div></li>'
        for a in items
    )
    return f'<ul class="checklist">{li}</ul>'


def _assumptions(draft: DraftGameSpec) -> str:
    return _assumptions_html(list(draft.assumptions))


def _sources_list(sources: list[FetchedSource]) -> str:
    """A linked list of fetched sources with retrieval dates (data about the evidence, D8.2).

    Hyperlinks reference the source pages; the report loads no external resource on open, so it
    stays self-contained and offline (D8.4).
    """
    items: list[str] = []
    for s in _sorted_sources(sources):
        title = _esc(s.title or s.url)
        link = f'<a href="{_esc(s.url)}" rel="noopener noreferrer">{title}</a>'
        meta = f'<div class="meta">{_esc(s.url)} · retrieved {_esc(s.retrieved_at)}</div>'
        # A source Claude fetched but never quoted has no snippet — flag it so a reviewer knows the
        # citation is weaker than one with quoted text (D9.0b).
        snip = (
            f'<div class="snip">{_esc(s.snippet)}</div>'
            if s.snippet
            else '<div class="snip flag">retrieved, not cited</div>'
        )
        items.append(f"<li>{link}{meta}{snip}</li>")
    return f'<ul class="sources">{"".join(items)}</ul>'


def _sorted_sources(sources: list[FetchedSource]) -> list[FetchedSource]:
    """Deterministic order for rendering (by url), independent of fetch order (D6.2)."""
    return sorted(sources, key=lambda s: s.url)


def _metric(value: str, label: str) -> str:
    return (
        f'<div class="metric"><div class="m-val">{_esc(value)}</div>'
        f'<div class="m-lab">{_esc(label)}</div></div>'
    )


def _dl(pairs: dict[str, str]) -> str:
    rows = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in pairs.items())
    return f"<dl>{rows}</dl>"


def render_forecast(record: ForecastRecord, *, rubric_source: str | None = None) -> str:
    """Render a ForecastRecord report.

    When the question carries a :class:`ResolutionRubric` (embedded, or resolved from its committed
    grading file and injected by the caller — D24.1), render the two-audience layered report
    (VERDICT / READING / ANALYST BRIEF / APPENDIX, D22.2); otherwise fall back to the standard
    full-analysis layout so rubric-less records render byte-identically (D22.5). ``rubric_source``
    is a human label stated in the appendix (e.g. the grading filename); None means embedded.
    """
    if record.game is not None and record.game.resolution_rubric is not None:
        return render_forecast_narrative(record, rubric_source=rubric_source)
    return _render_forecast_standard(record)


def _render_forecast_standard(record: ForecastRecord) -> str:
    """Render a ForecastRecord full-analysis report (the pre-D22 layout, unchanged)."""
    e = record.ensemble
    cv = record.convergence_stats
    frozen = record.game.frozen_at if record.game else "—"
    template = record.game.template if record.game else "—"
    parts = [
        f'<div class="kicker">Forecast analysis — {_esc(record.model)} model</div>',
        f"<h1>{_esc(record.question_id)}</h1>",
        f'<p class="sub">frozen {_esc(frozen)} · template: {_esc(template)} · '
        f"model: {_esc(record.model)}</p>",
        f'<p class="sub">run {_esc(record.run_id)}</p>',
    ]
    if record.live_searched:  # D9.0a — the inputs rest on a live search, not a frozen snapshot
        parts.append(
            '<div class="caveat"><strong>Live-searched inputs.</strong> This game was formalized '
            "with live web search on, so its inputs reflect the web as of the freeze date — not a "
            "record frozen in the past. Do not treat this as a clean historical backtest.</div>"
        )
    mode = record.median_trajectory[-1] if record.median_trajectory else None
    mode_metric = (
        _metric(f"{mode:.3f}", f"mode-game (gap {e.median - mode:+.2f})")
        if mode is not None
        else _metric("—", "mode-game median")
    )
    parts += [
        "<h2>Headline</h2>",
        '<div class="metrics">'
        + _metric(f"{e.median:.3f}", "MC median")
        + mode_metric
        + _metric(f"[{e.p10:.2f}, {e.p90:.2f}]", "CI80")
        + _metric(f"{e.mean:.3f}", "expected (mean)")
        + _metric(f"{cv.get('converged_fraction', 0.0) * 100:.0f}%", "converged")
        + "</div>",
    ]
    if record.game is not None:
        parts += [
            "<h2>Actor map &amp; settlement</h2>",
            f"<figure>{svg.actor_map(_actor_points(record.game), settlement=e.median)}</figure>",
        ]
    parts += [
        "<h2>Outcome distribution</h2>",
        "<figure>"
        + svg.histogram(record.outcome_distribution, p10=e.p10, p90=e.p90, median=e.median)
        + "</figure>",
        "<h2>Sensitivity — what to watch</h2>",
        _sensitivity_warning(record),
        f"<figure>{_tornado(record)}</figure>",
        "<h2>Median trajectory (deterministic mode game)</h2>",
        f"<figure>{svg.trajectory(record.median_trajectory)}</figure>",
    ]
    if record.game is not None:
        parts += ["<h2>Inputs</h2>", _actor_table(record.game, with_evidence=False)]
    if record.assumptions:
        parts += [
            "<h2>Assumptions carried from the draft — review</h2>",
            _assumptions_html(list(record.assumptions)),
        ]
    if record.analog_panel is not None:
        parts += [
            "<h2>Historical base rates — ICB analogs</h2>",
            _analog_panel(record.analog_panel),
        ]
    parts.append(_forecast_provenance(record))
    return _page(record.question_id, "".join(parts))


# --------------------------------------------------------------- two-audience narrative (D22.2)
def render_forecast_narrative(record: ForecastRecord, *, rubric_source: str | None = None) -> str:
    """The layered two-audience report: VERDICT / READING / ANALYST BRIEF / APPENDIX.

    All prose is deterministic template text composed from record fields plus the committed
    band and position-word vocabularies — no LLM anywhere (D22.3). Same record + same rubric =
    byte-identical output. ``rubric_source`` labels the rubric's origin in the appendix (D24.1).
    """
    if record.game is None:  # nothing to read without a game; degrade to the standard layout
        return _render_forecast_standard(record)
    game = record.game
    readout = map_bands(record)
    body = (
        _narr_verdict(record, game, readout)
        + _narr_reading(record, game, readout)
        + _narr_brief(record, game, readout)
        + precedent_panel_html(record)
        + _narr_appendix(record, rubric_source)
    )
    return _page(record.question_id, body, extra_css=_NARR_CSS)


def _precedent_segments(game: GameSpec, distribution: dict[str, float]) -> list[BandSeg]:
    """Threshold-tiled strip segments carrying the PRECEDENT distribution shares (D29.3)."""
    rubric = game.resolution_rubric
    assert rubric is not None
    bands = sorted(rubric.bands, key=lambda b: b.lo)
    los = [b.lo for b in bands]
    uppers = [*los[1:], 100.0]
    modal = max(distribution.items(), key=lambda kv: (kv[1], kv[0]))[0] if distribution else None
    return [
        BandSeg(
            lo=los[i],
            hi=uppers[i],
            share=distribution.get(b.label, 0.0),
            label=b.label,
            modal=(b.label == modal),
        )
        for i, b in enumerate(bands)
    ]


def precedent_panel_html(record: ForecastRecord) -> str:
    """The reference-class (outside-view) panel: the ratified precedents' distribution as its OWN
    strip beside the model's, clearly separated and NEVER blended (D29.3), plus the divergence
    diagnostic when the two disagree (D29.5). Guarded — empty when no panel is attached."""
    from schelling.precedents.panel import coverage_fraction, divergence_line

    panel = record.precedent_panel
    game = record.game
    if panel is None or game is None or game.resolution_rubric is None:
        return ""
    pal = load_palette()
    parts = ['<section class="narr"><h2>Reference class — the outside view</h2>']
    if panel.reference_class:
        parts.append(f"<p class='sub'>Reference class: {_esc(panel.reference_class)}.</p>")
    if not panel.complete:
        # Sessions-at-risk could not be fully sourced: report coverage, NOT a base rate (D30.1).
        frac = coverage_fraction(panel)
        denom = str(panel.sessions_at_risk) if panel.sessions_at_risk is not None else "unknown"
        cov = f" ({frac:.0%} of the class)" if frac is not None else ""
        parts.append(
            f'<div class="caveat"><strong>INCOMPLETE reference class.</strong> {panel.n_covered} '
            f"of {denom} sessions-at-risk are covered{cov}. The reference class is sessions-at-risk"
            " (every decision opportunity, including sessions that decided nothing), not notable "
            "outcomes. Because the full population could not be sourced, <strong>no base rate is "
            "computed</strong> — a distribution over a biased sample would overstate action.</div>"
        )
    else:
        parts.append(
            f"<p class='sub'>The empirical distribution over the full sessions-at-risk class of "
            f"<strong>{panel.n_covered}</strong> ratified, ex-ante-codable decision opportunities "
            "(including no-action sessions). This is a base rate, <strong>not</strong> a forecast, "
            f"and is <strong>never blended</strong> (weight {panel.blend_weight:g}) — "
            "shown beside the model strip for comparison only.</p>"
        )
        diverge = divergence_line(record)
        if diverge:
            parts.append(f'<div class="caveat"><strong>{_esc(diverge)}</strong></div>')
        desc = "Distribution of ratified precedents across the rubric bands (outside view)."
        strip = svg.band_strip(
            _precedent_segments(game, panel.band_distribution),
            median=panel.median_placement if panel.median_placement is not None else 50.0,
            p10=min((p.proposed_placement for p in panel.precedents), default=0.0),
            p90=max((p.proposed_placement for p in panel.precedents), default=100.0),
            palette=pal,
            desc=desc,
        )
        parts.append(f"<figure>{strip}</figure>")
    rows = "".join(
        f"<tr><td>{_esc(p.what_happened)}</td><td class='num'>{_esc(p.date)}</td>"
        f"<td class='num'>{p.proposed_placement:g}</td><td>{_esc(p.source)}</td>"
        f"<td class='ev'>{_esc(p.reasoning)}</td></tr>"
        for p in panel.precedents
    )
    parts.append(
        "<table><thead><tr><th>what happened</th><th>date</th><th>placement</th><th>source</th>"
        f"<th>why</th></tr></thead><tbody>{rows}</tbody></table>"
    )
    if panel.hindsight_precedents:
        parts.append(
            f"<p class='sub'><strong>Reported separately — {len(panel.hindsight_precedents)} "
            "hindsight-coded precedent(s)</strong> (coded with knowledge of their own outcome; "
            "excluded from the base rate): "
            + "; ".join(_esc(p.what_happened) for p in panel.hindsight_precedents)
            + ".</p>"
        )
    parts.append(f"<p class='sub'>Ratification: <em>{_esc(panel.ratification_note)}</em></p>")
    parts.append("</section>")
    return "".join(parts)


def _what_would_change(record: ForecastRecord, game: GameSpec) -> str:
    """The single highest-swing parameter (tornado top), or a weight-based fallback for the
    compromise model, which has no tornado."""
    by_id = {a.id: a for a in game.actors}
    if record.sensitivity:
        top = max(record.sensitivity, key=lambda s: abs(s.swing))
        actor = by_id.get(top.actor_id)
        who = _short_name(game, actor) if actor is not None else top.actor_id
        return (
            f"<p><strong>What would change this:</strong> {_esc(who)}'s {_esc(top.field)} — moving "
            f"it across its stated range swings the forecast by {top.swing:+.1f} points "
            f"({top.forecast_at_low:.0f} to {top.forecast_at_high:.0f}).</p>"
        )
    # Fallback: the heaviest-weight actor whose position range is widest is the input to watch.
    ranked = sorted(
        game.actors,
        key=lambda a: (a.capability.mode * a.salience.mode) * (a.position.high - a.position.low),
        reverse=True,
    )
    a = ranked[0]
    return (
        f"<p><strong>What would change this:</strong> {_esc(_short_name(game, a))}'s position — it "
        f"carries the heaviest weight, and its stated range runs "
        f"{a.position.low:g} to {a.position.high:g}.</p>"
    )


def _band_segments(readout: BandReadout) -> list[BandSeg]:
    """Threshold-tiled strip segments from the banded readout: segment i spans [lo_i, lo_{i+1}]
    (last to 100), matching the band-membership rule so the strip tiles 0-100 with no gaps."""
    per = readout.per_band
    los = [bp.band.lo for bp in per]
    uppers = [*los[1:], 100.0]
    return [
        BandSeg(
            lo=los[i], hi=uppers[i], share=bp.probability, label=bp.band.label, modal=bp.is_modal
        )
        for i, bp in enumerate(per)
    ]


def _verdict_strip(record: ForecastRecord, readout: BandReadout) -> str:
    """The band-probability strip (banded rubric) or continuous density strip (arithmetic/none),
    with a one-line legend. A pure function of the record + rubric (D23.1)."""
    pal = load_palette()
    e = record.ensemble
    if readout.kind == BANDED and readout.per_band:
        modal = readout.modal_band
        modal_prob = next((bp.probability for bp in readout.per_band if bp.is_modal), 0.0)
        modal_label = modal.label if modal is not None else "the modal band"
        desc = (
            f"Band-probability strip: {modal_label} is the most likely outcome at "
            f"{format_share(modal_prob)} of {e.n_draws} draws; the median is {e.median:.0f} of 100."
        )
        fig = svg.band_strip(
            _band_segments(readout), median=e.median, p10=e.p10, p90=e.p90, palette=pal, desc=desc
        )
        legend = (
            "Segment width tracks each band's span; fill darkness is its share of the draws; the "
            "outlined band is the most likely. Beneath: &#9650; median, bracket = 80% CI."
        )
    else:
        if not record.outcome_distribution:
            return ""  # graceful: nothing to draw without cached draws
        desc = (
            f"Outcome density across the 0-100 scale; median {e.median:.0f}, 80% of draws between "
            f"{e.p10:.0f} and {e.p90:.0f}."
        )
        fig = svg.density_strip(
            record.outcome_distribution,
            median=e.median,
            p10=e.p10,
            p90=e.p90,
            palette=pal,
            desc=desc,
        )
        legend = (
            "Arithmetic rubric: a continuous density of the draws (darker = denser). Beneath: "
            "&#9650; median, bracket = 80% CI."
        )
    return f"<figure>{fig}</figure><p class='legend'>{legend}</p>"


def _reading_diagram(record: ForecastRecord, game: GameSpec) -> str:
    """The weighted-actor diagram + a one-line legend. Pure function of the record (D23.2)."""
    pal = load_palette()
    non_voting = set(game.non_voting_actor_ids)
    actors = [
        WActor(
            name=_short_name(game, a),
            position=a.position.mode,
            weight=a.capability.mode * a.salience.mode,
            non_voting=a.id in non_voting,
        )
        for a in game.actors
    ]
    e = record.ensemble
    desc = (
        f"Actors on the 0-100 scale sized by capability times salience; the settlement is at "
        f"{e.median:.0f} of 100."
    )
    fig = svg.weighted_actors(actors, settlement=e.median, palette=pal, desc=desc)
    # Fixed, direction-derived legend phrases — never truncated anchor prose (D25.4).
    legend_bits = [
        "Circle area &#8733; capability&times;salience.",
        "Amber = the low half (toward 0); teal = the high half (toward 100).",
    ]
    if non_voting:
        legend_bits.append("Dashed ring + * = non-voting / out-of-body influence.")
    return f"<figure>{fig}</figure><p class='legend'>{' '.join(legend_bits)}</p>"


def _narr_verdict(record: ForecastRecord, game: GameSpec, readout: BandReadout) -> str:
    e = record.ensemble
    parts = [
        '<section class="narr verdict-sec"><div class="kicker">Verdict</div>',
        f"<h1>{_esc(record.question_id)}</h1>",
        f'<p class="sub">frozen {_esc(game.frozen_at)} · {_esc(record.model)} model · '
        f"run {_esc(record.run_id)}</p>",
    ]
    if record.live_searched:
        parts.append(
            '<div class="caveat"><strong>Live-searched inputs.</strong> Formalized with web search '
            "on, so the inputs reflect the web as of the freeze date — not a clean historical "
            "backtest.</div>"
        )
    banded = readout.kind == BANDED and readout.modal_band is not None
    if banded and readout.median_band is not None and readout.modal_band is not None:
        modal_prob = next(bp.probability for bp in readout.per_band if bp.is_modal)
        mb = readout.median_band
        parts.append(
            f'<p class="lede">Most likely: <strong>{_esc(readout.modal_band.label)}</strong> — '
            f"{format_share(modal_prob)} of {e.n_draws} simulated draws. The forecast median is "
            f"{e.median:.0f} on the 0-100 scale, in the band &ldquo;{_esc(mb.label)}&rdquo; "
            f"({mb.lo:g}&ndash;{mb.hi:g}).</p>"
        )
    else:
        parts.append(
            f'<p class="lede">The forecast median is <strong>{e.median:.0f}</strong> on the 0-100 '
            f"scale (CI80 [{e.p10:.0f}, {e.p90:.0f}]). {_esc(readout.note)}</p>"
        )
    parts.append(f'<p class="scope">{_SHARE_SCOPE}</p>')  # standing scope note (D25.2)
    parts.append(_verdict_strip(record, readout))
    parts.append(_what_would_change(record, game))
    parts.append("</section>")
    return "".join(parts)


def _widest_inputs(game: GameSpec, k: int) -> list[tuple[str, str, float, float]]:
    """The ``k`` widest input ranges (short name, field, low, high), most uncertain first."""
    rows: list[tuple[str, str, float, float]] = []
    for a in game.actors:
        fields = (("position", a.position), ("salience", a.salience), ("capability", a.capability))
        for field, est in fields:
            rows.append((_short_name(game, a), field, est.low, est.high))
    rows.sort(key=lambda r: r[3] - r[2], reverse=True)
    return rows[:k]


_COUNT_WORD = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}


def _join(names: list[str]) -> str:
    """Join names as ``A``, ``A and B``, ``A, B and C``."""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _player_items(game: GameSpec) -> str:
    """The players list, grouped: actors sharing a side (position third) and salience tier become
    one sentence instead of one identical sentence each (D25.5)."""
    v = load_vocab()
    groups: list[tuple[str, str, list[str]]] = []
    index: dict[tuple[str, str], int] = {}
    for a in game.actors:
        pos = phrase_for(a.position.mode, v.position_thirds)
        sal = phrase_for(a.salience.mode, v.salience_thirds)
        key = (pos, sal)
        if key not in index:
            index[key] = len(groups)
            groups.append((pos, sal, []))
        groups[index[key]][2].append(_short_name(game, a))
    items: list[str] = []
    for pos, sal, names in groups:
        if len(names) == 1:
            items.append(
                f"<li><strong>{_esc(names[0])}</strong> sits {_esc(pos)}; "
                f"the outcome is {_esc(sal)}.</li>"
            )
        else:
            count = _COUNT_WORD.get(len(names), str(len(names)))
            joined = _join([_esc(n) for n in names])
            sal_each = _esc(sal).replace(" for it", " for each")
            items.append(
                f"<li>{count} members sit {_esc(pos)}: <strong>{joined}</strong> "
                f"&mdash; {sal_each}.</li>"
            )
    return "".join(items)


def _narr_reading(record: ForecastRecord, game: GameSpec, readout: BandReadout) -> str:
    v = load_vocab()
    c = game.continuum
    e = record.ensemble
    parts = [
        '<section class="narr"><h2>Reading</h2>',
        f"<p>The scale runs 0 to 100. <strong>0</strong> means {_esc(c.anchor_0)}. "
        f"<strong>100</strong> means {_esc(c.anchor_100)}. The forecast sits at {e.median:.0f} — "
        f"{_esc(phrase_for(e.median, v.position_thirds))}.</p>",
    ]
    parts.append(f"<p>The players and where they stand:</p><ul>{_player_items(game)}</ul>")
    parts.append(_reading_diagram(record, game))
    weights = [(a, a.capability.mode * a.salience.mode) for a in game.actors]
    total = sum(w for _, w in weights) or 1.0
    heaviest = sorted(weights, key=lambda x: (-x[1], x[0].id))[:2]
    heavy_desc = " and ".join(
        f"{_esc(_short_name(game, a))} ({w / total:.0%} of the weight)" for a, w in heaviest
    )
    cp = compromise_point(game)
    parts.append(
        f"<p>The settlement is a capability&times;salience weighted average of these positions. "
        f"The heaviest weights sit with {heavy_desc}, pulling the result "
        f"{_esc(phrase_for(heaviest[0][0].position.mode, v.position_thirds))}. The closed-form "
        f"weighted mean lands at {cp:.0f}.</p>"
    )
    unc = "; ".join(
        f"{_esc(name)}'s {field} (anywhere from {lo:g} to {hi:g})"
        for name, field, lo, hi in _widest_inputs(game, 3)
    )
    parts.append(f"<p><strong>Genuinely uncertain:</strong> {unc}.</p></section>")
    return "".join(parts)


def _narr_solvers(record: ForecastRecord, game: GameSpec, readout: BandReadout) -> str:
    """The two solvers side by side — never blended (D22.5)."""
    e = record.ensemble
    rubric = game.resolution_rubric
    cp = compromise_point(game)
    this_band = readout.median_band
    cp_band = band_containing(cp, rubric)

    def band_label(b: RubricBand | None) -> str:
        return _esc(b.label) if b is not None else "—"

    rows = (
        f"<tr><td>this run ({_esc(record.model)})</td><td class='num'>{e.median:.1f}</td>"
        f"<td>{band_label(this_band)}</td></tr>"
        f"<tr><td>compromise weighted-mean (closed form)</td><td class='num'>{cp:.1f}</td>"
        f"<td>{band_label(cp_band)}</td></tr>"
    )
    gap = abs(e.median - cp)
    same = this_band is not None and cp_band is not None and this_band.lo == cp_band.lo
    agree = "land in the same band" if same else "land in different bands"
    return (
        "<h3>Both solvers, side by side</h3><table><thead><tr><th>model</th><th>median</th>"
        f"<th>band</th></tr></thead><tbody>{rows}</tbody></table>"
        f"<p class='sub'>The two solvers differ by {gap:.1f} points and {agree}. Their outputs are "
        "shown side by side, never blended into one number.</p>"
    )


def _narr_assumptions_split(record: ForecastRecord, game: GameSpec) -> str:
    """Inputs split into what a source establishes vs what was inferred (rule 6)."""
    sourced = [a for a in game.actors if a.evidence]
    parts = ["<h3>What rests on sources vs inference</h3>"]
    if sourced:
        li = "".join(
            f"<li><strong>{_esc(a.name)}</strong> — {len(a.evidence)} evidence note(s)</li>"
            for a in sourced
        )
        parts.append(
            "<p><strong>Sourced</strong> — traces to fetched sources or supplied text:</p>"
            f"<ul>{li}</ul>"
        )
    else:
        parts.append(
            "<p><strong>Sourced:</strong> <span class='sub'>none — no evidence notes on any "
            "actor.</span></p>"
        )
    parts.append("<p><strong>Inferred</strong> — asserted where the sources were silent:</p>")
    parts.append(_assumptions_html(list(record.assumptions)))
    return "".join(parts)


def _narr_diagnostics(record: ForecastRecord) -> str:
    e = record.ensemble
    cv = record.convergence_stats
    mode = record.median_trajectory[-1] if record.median_trajectory else None
    degen = zero_swing_warning(record.sensitivity)
    pairs = {
        "converged fraction": f"{cv.get('converged_fraction', 0.0) * 100:.0f}%",
        "mode-game median": (
            f"{mode:.1f} (gap {e.median - mode:+.1f})" if mode is not None else "—"
        ),
        "degenerate lock": degen or "none",
    }
    return "<h3>Diagnostics</h3>" + _dl(pairs)


def _narr_brief(record: ForecastRecord, game: GameSpec, readout: BandReadout) -> str:
    e = record.ensemble
    parts = ['<section class="narr"><h2>Analyst brief</h2>']
    if readout.kind == BANDED:
        rows = ""
        for bp in readout.per_band:
            marks = [m for m, on in (("modal", bp.is_modal), ("median", bp.is_median)) if on]
            mark = f" <span class='ev'>({', '.join(marks)})</span>" if marks else ""
            cls = " class='modal'" if bp.is_modal else ""
            rows += (
                f"<tr{cls}><td>{_esc(bp.band.label)}{mark}</td>"
                f"<td class='num'>{bp.band.lo:g}&ndash;{bp.band.hi:g}</td>"
                f"<td class='num'>{format_share(bp.probability)}</td></tr>"
            )
        parts.append(
            "<h3>Band probabilities</h3><table><thead><tr><th>band</th><th>range</th>"
            f"<th>P(draws)</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    else:
        parts.append(f"<h3>Band probabilities</h3><p class='sub'>{_esc(readout.note)}</p>")
    parts.append(_narr_solvers(record, game, readout))
    parts.append(
        "<h3>Outcome distribution</h3><figure>"
        + svg.histogram(record.outcome_distribution, p10=e.p10, p90=e.p90, median=e.median)
        + "</figure>"
    )
    parts.append("<h3>Stakeholders &amp; evidence</h3>" + _actor_table(game, with_evidence=True))
    parts.append(_narr_assumptions_split(record, game))
    parts.append("<h3>What to watch — sensitivity</h3>")
    parts.append(_sensitivity_warning(record))
    if record.sensitivity:
        parts.append(f"<figure>{_tornado(record)}</figure>")
    else:
        parts.append(
            "<p class='sub'>The compromise weighted-mean model has no round-by-round tornado; "
            "see the widest input ranges under Reading.</p>"
        )
    parts.append(_narr_diagnostics(record))
    parts.append("</section>")
    return "".join(parts)


def _narr_appendix(record: ForecastRecord, rubric_source: str | None = None) -> str:
    parts = ['<section class="narr"><h2>Appendix</h2>']
    # State where the grading rubric came from (D24.1): embedded in the record, or resolved from the
    # committed grading file at render time (the record itself is never modified).
    src = (
        "embedded in the record"
        if rubric_source is None
        else f"resolved at render time from {_esc(rubric_source)} (the record was not modified)"
    )
    parts.append(f"<h3>Rubric source</h3><p class='sub'>{src}.</p>")
    if record.sources_fetched:
        parts.append(
            f"<h3>Sources fetched ({len(record.sources_fetched)})</h3>"
            + _sources_list(record.sources_fetched)
        )
    else:
        parts.append(
            "<h3>Sources fetched</h3><p class='sub'>None carried into this record "
            "(bare GameSpec, or the draft was not live-searched).</p>"
        )
    cmd = (
        f"schelling solve &lt;game&gt;.json --seed {record.seed} "
        f"--solver {record.model} --draws {record.ensemble.n_draws}"
    )
    parts.append(f"<h3>Reproduce</h3><pre>{cmd}</pre>")
    pairs = {
        "inputs_hash": record.inputs_hash,
        "engine (git SHA)": record.engine_version,
        "seed": str(record.seed),
        "model": record.model,
        "n_draws": str(record.ensemble.n_draws),
    }
    parts.append(_dl(pairs))
    fm = record.formalizer_metadata
    if fm is not None:
        parts.append(
            f"<p class='sub'>Formalized by {_esc(fm.model)} · {fm.searches_used} search(es) · "
            f"${fm.cost_usd:.4f}</p>"
        )
    parts.append("</section>")
    return "".join(parts)


def _analog_panel(panel: AnalogPanel) -> str:
    """A base-rate panel, clearly separated from the solver line (blend weight disclosed, D11.2)."""
    q = ", ".join(f"{k} {v:g}" for k, v in panel.query.items())
    bars = [BarRow(f"{label}", frac) for label, frac in panel.outcome_distribution.items()]
    rows = "".join(
        f"<tr><td>{_esc(e.crisname)}</td><td class='num'>{e.year}</td>"
        f"<td>{_esc(e.actor)}</td><td>{_esc(e.outcome)}</td></tr>"
        for e in panel.examples
    )
    return (
        f'<p class="sub">Base rate over the <strong>{panel.n}</strong> most structurally similar '
        f"ICB crises ({_esc(q)}). A historical frequency, <strong>not</strong> a forecast — "
        f"<strong>not blended</strong> into the forecast (weight {panel.blend_weight:g}).</p>"
        f"<figure>{svg.hbars(bars)}</figure>"
        "<table><thead><tr><th>analog crisis</th><th>year</th><th>actor</th><th>outcome</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>"
        f'<p class="cite">Source: {_esc(panel.source)}</p>'
    )


def _sensitivity_warning(record: ForecastRecord) -> str:
    """A caveat box when the tornado is dominated by zero-swing rows (degenerate lock, D12.3)."""
    warning = zero_swing_warning(record.sensitivity)
    return f'<div class="caveat">{_esc(warning)}</div>' if warning else ""


def _tornado(record: ForecastRecord) -> str:
    baseline = record.median_trajectory[-1] if record.median_trajectory else record.ensemble.median
    rows = [
        TornadoRow(s.parameter, s.forecast_at_low, s.forecast_at_high, s.swing)
        for s in record.sensitivity
    ]
    return svg.tornado(rows, baseline=baseline)


def _forecast_provenance(record: ForecastRecord) -> str:
    cfg = "  ".join(f"{k}={record.solver_config[k]}" for k in sorted(record.solver_config))
    pairs = {
        "seed": str(record.seed),
        "n_draws": str(record.ensemble.n_draws),
        "inputs_hash": record.inputs_hash,
        "engine": record.engine_version,
        "solver_config": cfg,
    }
    fm = record.formalizer_metadata
    if fm is not None:  # provenance chain: the formalize call that produced the game
        pairs["formalizer"] = (
            f"{fm.model}  in {fm.input_tokens} · out {fm.output_tokens} tok  "
            f"${fm.cost_usd:.4f}  (retries {fm.retries}, leak {fm.leak_retries})"
        )
    return f'<div class="prov">Provenance{_dl(pairs)}</div>'


def _own_moves_table(moves: list[OwnMove]) -> str:
    rows = "".join(
        f"<tr><td>{_esc(m.dimension)}</td><td class='num'>{m.value:g}</td>"
        f"<td class='num'>{m.settlement_median:.3f}</td>"
        f"<td class='num'>{m.benefit:+.3f}</td><td class='num'>{m.cost:g}</td>"
        f"<td>{'<span class="flag">beyond stated range</span>' if m.beyond_stated_range else ''}"
        "</td></tr>"
        for m in moves
    )
    return (
        "<table><thead><tr><th>move</th><th>to</th><th>settlement</th><th>benefit</th>"
        f"<th>cost</th><th></th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _targets_table(targets: list[PersuasionTarget]) -> str:
    rows = "".join(
        f"<tr><td>{_esc(t.actor_id)}</td><td>{_esc(t.dimension)}</td>"
        f"<td>{_esc(t.kind)}</td>"
        f"<td class='num'>{t.from_value:g} &rarr; {t.to_value:g}</td>"
        f"<td class='num'>{t.settlement_median:.3f}</td><td class='num'>{t.benefit:+.3f}</td></tr>"
        for t in targets
    )
    return (
        "<table><thead><tr><th>actor</th><th>lever</th><th>play</th><th>shift</th>"
        f"<th>settlement</th><th>benefit</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def render_advise(record: AdviseRecord) -> str:
    """Render an AdviseRecord: baseline map, own-moves benefit/cost, persuasion ranking, caveat."""
    lens = "exact weighted-mean (closed-form)" if record.exact else "simulated challenge (MC)"
    parts = [
        '<div class="kicker">Strategic advice — one-sided lever search</div>',
        f"<h1>{_esc(record.question_id)}</h1>",
        f'<p class="sub">advising <strong>{_esc(record.advising_actor)}</strong> · '
        f"ideal {record.ideal:g} · baseline settlement {record.baseline_median:.3f}</p>",
        f'<div class="caveat"><strong>Caveat.</strong> '
        f"{_esc(SUCCESSOR_CAVEAT if record.mode == 'equilibrium' else ADVISE_CAVEAT)}</div>",
    ]
    if record.exact or record.second_lens is not None:
        parts.append(f'<p class="sub">Primary lever lens: <strong>{lens}</strong>.</p>')
    if record.game is not None:
        amap = svg.actor_map(_actor_points(record.game), settlement=record.baseline_median)
        parts += ["<h2>Baseline actor map &amp; settlement</h2>", f"<figure>{amap}</figure>"]
    scatter_pts = [ScatterPoint(m.cost, m.benefit, "") for m in record.own_moves]
    parts += [
        "<h2>Own moves — benefit (toward ideal) vs. cost conceded</h2>",
        f"<figure>{svg.scatter(scatter_pts, x_label='cost', y_label='benefit')}</figure>",
        "<h2>Top own moves</h2>",
        _own_moves_table(record.top_moves),
    ]
    bars = [
        BarRow(f"{t.actor_id}.{t.dimension} ({t.kind})", t.benefit)
        for t in record.persuasion_targets[:8]
    ]
    parts += [
        "<h2>Who to work on — persuasion targets</h2>",
        f"<figure>{svg.hbars(bars)}</figure>",
        _targets_table(record.persuasion_targets),
    ]
    if record.second_lens is not None:
        s = record.second_lens
        label = "exact (closed-form)" if s.exact else "simulated"
        parts += [
            f"<h2>Second lens — {_esc(s.model)} model, {label}</h2>",
            f'<p class="sub">Baseline settlement {s.baseline_median:.3f}. Shown side by side so '
            "the two models' levers can be compared.</p>",
            _own_moves_table(s.top_moves),
            _targets_table(s.persuasion_targets),
        ]
    parts.append(_strategy_sections(record))
    parts.append(_advise_provenance(record))
    return _page(record.question_id, "".join(parts))


def _strategy_sections(record: AdviseRecord) -> str:
    """Advise 2.0 report sections — all guarded so pre-2.0 records render byte-identically."""
    out: list[str] = []
    detailed = [m for m in record.top_moves if m.response or m.robustness or m.action]
    if detailed:
        rows = ""
        for m in detailed:
            act = _esc(m.action.name) if m.action else "&mdash;"
            if m.response is not None:
                sim = " (sim)" if m.response.simulated else ""
                resp = (
                    f"{m.response.gross_benefit:+.3f} &rarr; {m.response.net_benefit:+.3f} "
                    f"vs {_esc(m.response.responder_id)}{sim}"
                )
            else:
                resp = "&mdash;"
            rob = (
                f"{_esc(m.robustness.grade)} ({m.robustness.sign_stable_fraction:.0%})"
                if m.robustness
                else "&mdash;"
            )
            rows += (
                f"<tr><td>{_esc(m.dimension)} &rarr; {m.value:g}</td><td>{act}</td>"
                f"<td class='num'>{resp}</td><td>{rob}</td></tr>"
            )
        out.append(
            "<h2>Response preview &amp; robustness</h2><table><thead><tr><th>move</th>"
            "<th>action</th><th>gross &rarr; net (responder)</th><th>robustness</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    if record.packages:
        rows = "".join(
            f"<tr><td>{_esc(' + '.join(p.moves))}</td>"
            f"<td class='num'>{p.settlement_median:.3f}</td>"
            f"<td class='num'>{p.benefit:+.3f}</td><td class='num'>{p.cost:g}</td>"
            f"<td>{_esc(p.robustness.grade) if p.robustness else ''}</td></tr>"
            for p in record.packages
        )
        out.append(
            "<h2>Best two-move packages (exact lens)</h2><table><thead><tr><th>package</th>"
            "<th>settlement</th><th>benefit</th><th>cost</th><th>robustness</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    if record.equilibrium is not None:
        eq = record.equilibrium
        status = (
            "cycle detected" if eq.cycle else ("converged" if eq.converged else "did not settle")
        )
        mrows = "".join(
            f"<tr><td>{_esc(m.actor_id)}</td>"
            f"<td class='num'>{m.position_from:g} &rarr; {m.position_to:g}</td>"
            f"<td class='num'>{m.salience_from:g} &rarr; {m.salience_to:g}</td></tr>"
            for m in eq.moves
        )
        path = _esc(str([round(x, 2) for x in eq.path]))
        out.append(
            f"<h2>Equilibrium &mdash; iterated best responses</h2>"
            f'<p class="sub">{status}, {eq.iterations} iterations; settlement '
            f"{eq.settlement:.3f}. Path: {path}.</p>"
            "<table><thead><tr><th>actor</th><th>position</th><th>salience</th></tr></thead>"
            f"<tbody>{mrows}</tbody></table>"
        )
    if record.strategy_brief:
        out.append(
            f'<div class="brief"><h2>Strategy brief</h2><p>{_esc(record.strategy_brief)}</p></div>'
        )
    return "".join(out)


def _advise_provenance(record: AdviseRecord) -> str:
    adv = "  ".join(f"{k}={record.advise_config[k]}" for k in sorted(record.advise_config))
    cfg = "  ".join(f"{k}={record.solver_config[k]}" for k in sorted(record.solver_config))
    pairs = {
        "seed": str(record.seed),
        "baseline": record.baseline_run_id,
        "inputs_hash": record.inputs_hash,
        "engine": record.engine_version,
        "advise_config": adv,
        "solver_config": cfg,
    }
    return f'<div class="prov">Provenance{_dl(pairs)}</div>'


def _pct(sorted_vals: list[float], q: float) -> float:
    """Deterministic percentile (linear interpolation) of an already-sorted list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q / 100.0 * (len(sorted_vals) - 1)
    lo = int(pos)
    frac = pos - lo
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _mae_bars(record: BacktestRecord) -> str:
    return svg.hbars([BarRow(m.label, m.mae) for m in record.methods])


def _method_table(record: BacktestRecord) -> str:
    rows = []
    for m in record.methods:
        cls = ' class="primary"' if m.key == record.primary_method else ""
        mark = " ★" if m.key == record.primary_method else ""
        rows.append(
            f"<tr{cls}><td>{_esc(m.label)}{mark}</td><td>{_esc(m.kind)}</td>"
            f"<td class='num'>{m.mae:.2f}</td><td class='num'>{m.rmse:.2f}</td>"
            f"<td class='num'>{m.median_error:.2f}</td><td class='num'>{m.max_error:.2f}</td></tr>"
        )
    return (
        "<table><thead><tr><th>method</th><th>kind</th><th>MAE</th><th>RMSE</th>"
        f"<th>median AE</th><th>max AE</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _worst_table(record: BacktestRecord) -> str:
    rows = "".join(
        f"<tr><td>{_esc(w.issue_id)}</td><td>{_esc(w.proposal_name[:48])}</td>"
        f"<td class='num'>{w.forecast:.1f}</td><td class='num'>{w.actual:.1f}</td>"
        f"<td class='num'>{w.error:.1f}</td></tr>"
        for w in record.worst_issues
    )
    return (
        "<table><thead><tr><th>issue</th><th>proposal</th><th>forecast</th><th>actual</th>"
        f"<th>error</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _context_table() -> str:
    rows = "".join(
        f"<tr><td>{_esc(p.model)}</td><td class='num'>{p.mean_abs_error:.1f}</td>"
        f"<td>{_esc(p.subset)}</td><td>{_esc(p.source)}</td></tr>"
        for p in PUBLISHED_RESULTS
    )
    cites = "".join(f"<li class='cite'>{_esc(c)}</li>" for c in CITATIONS)
    return (
        "<table><thead><tr><th>published model</th><th>mean abs error</th><th>subset</th>"
        f"<th>source</th></tr></thead><tbody>{rows}</tbody></table>"
        f"<ul>{cites}</ul>"
    )


def _split_table(record: BacktestRecord) -> str:
    s = record.split_sample
    if s is None:
        return ""
    verdict = "beats" if s.passed else "does NOT beat"
    return (
        f'<p class="sub">Tuned <strong>{_esc(s.tuned_param)}</strong> = {s.selected:g} on '
        f"{s.train_n} train issues (candidates {_esc(', '.join(f'{c:g}' for c in s.candidates))}), "
        f"scored on {s.test_n} held-out issues. On the held-out half the tuned model "
        f"(MAE {s.test_mae:.2f}) <strong>{verdict}</strong> the equally-equipped weighted mean "
        f"(MAE {s.test_baseline_mae:.2f}) — the improvement is {'' if s.passed else 'not '}enough, "
        f"and it is not an artifact of tuning.</p>"
    )


def render_backtest(record: BacktestRecord) -> str:
    """Render a BacktestRecord: gate verdict, per-method MAE, error histogram, worst issues."""
    primary = next(m for m in record.methods if m.key == record.primary_method)
    baselines = [next(m for m in record.methods if m.key == k) for k in record.baseline_methods]
    verdict_cls = "pass" if record.gate_passed else "fail"
    verdict_txt = "PASSED" if record.gate_passed else "FAILED"
    b_txt = "; ".join(f"{b.label.split('—')[-1].strip()} {b.mae:.2f}" for b in baselines)

    errors = sorted(primary.errors)
    p10, p90 = _pct(errors, 10), _pct(errors, 90)
    cap_txt = (
        "sourced treaty-regime capabilities"
        if record.capability_mode == "sourced"
        else f"equal capability {record.capability:g}"
    )

    parts = [
        '<div class="kicker">Backtest — DEU benchmark</div>',
        f"<h1>{_esc(record.dataset)}</h1>",
        f'<p class="sub">{record.n_issues} resolved issues · search off (frozen benchmark) · '
        f"{_esc(cap_txt)}</p>",
        f'<div class="verdict {verdict_cls}">Gate {verdict_txt}: the primary challenge model '
        f"(MAE {primary.mae:.2f}) must beat both baselines ({_esc(b_txt)}).</div>",
        "<h2>Mean absolute error by method</h2>",
        f"<figure>{_mae_bars(record)}</figure>",
        _method_table(record),
    ]
    if record.oracle is not None:
        o = record.oracle
        near = "at/near the ceiling" if o.gap <= 1.0 else f"below the ceiling by {o.gap:.2f}"
        parts += [
            "<h2>Noise-floor oracle — DIAGNOSTIC</h2>",
            f'<p class="sub">A flexible cross-validated model ({_esc(o.best_model)}, '
            f"{o.folds}-fold, rich features incl. positions) scores MAE "
            f"<strong>{o.oracle_mae:.2f}</strong> — the "
            f"extractable-signal ceiling. The compromise mean scores <strong>{o.compromise_mae:.2f}"
            f"</strong> (gap {o.gap:+.2f}): the mean is <strong>{near}</strong>.</p>",
        ]
    if record.split_sample is not None:
        parts += [
            "<h2>Split-sample validation of the rp-anchored tuning</h2>",
            _split_table(record),
        ]
    parts += [
        "<h2>Error distribution — primary model</h2>",
        "<figure>"
        + svg.histogram(primary.errors, p10=p10, p90=p90, median=primary.median_error)
        + "</figure>",
        "<h2>Worst issues — for inspection</h2>",
        _worst_table(record),
        "<h2>Published DEU error rates — for context</h2>",
        f'<p class="sub">{_esc(CONTEXT_PROSE)}</p>',
        _context_table(),
    ]
    prov = _dl(
        {
            "dataset_sha256": record.dataset_sha256,
            "engine": record.engine_version,
            "seed": str(record.seed),
            "n_issues": str(record.n_issues),
        }
    )
    parts.append(f'<div class="prov">Provenance{prov}</div>')
    return _page(f"Backtest — {record.dataset}", "".join(parts))


def _looks_like_backtest(data: dict[str, Any]) -> bool:
    return "methods" in data and "gate_passed" in data and "primary_method" in data


def _fmt_err(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
    return f"{loc}: {err.get('msg', 'invalid')}"


def _looks_like_llm_forecast(data: dict[str, Any]) -> bool:
    return "judge_model" in data and "samples" in data


def _looks_like_forecast(data: dict[str, Any]) -> bool:
    return "run_id" in data and any(
        k in data for k in ("ensemble", "forecast_median", "outcome_distribution")
    )


def render_llm_forecast(record: LLMForecastRecord) -> str:
    """Render an LLM judgment baseline: headline, samples, band probabilities, provenance appendix.

    The appendix states plainly that this is a model judgment and that re-running produces different
    samples — the file SHA-256 is the commitment (D27.2)."""
    e = record.ensemble
    parts = [
        '<div class="kicker">LLM judgment baseline — direct model forecast (no solver)</div>',
        f"<h1>{_esc(record.question_id)}</h1>",
        f'<p class="sub">{_esc(record.judge_model)} · {record.n_samples} samples · '
        f"temperature {record.temperature:g}</p>",
    ]
    if record.contamination_risk:
        parts.append(
            f'<div class="caveat"><strong>Contamination risk.</strong> '
            f"{_esc(record.contamination_note)}</div>"
        )
    parts += [
        "<h2>Headline</h2>",
        '<div class="metrics">'
        + _metric(f"{e.median:.1f}", f"median of {record.n_samples} samples")
        + _metric(f"[{e.p10:.0f}, {e.p90:.0f}]", "80% interval")
        + _metric(f"{record.self_consistency:.1f}", "self-consistency (spread)")
        + "</div>",
    ]
    if record.band_probabilities:
        rows = "".join(
            f"<tr><td>{_esc(k)}</td><td class='num'>{v:.0%}</td></tr>"
            for k, v in sorted(record.band_probabilities.items(), key=lambda kv: -kv[1])
        )
        parts.append(
            "<h2>Band probabilities (model's own)</h2><table><thead><tr><th>band</th>"
            f"<th>P</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    srows = "".join(
        f"<tr><td class='num'>{i + 1}</td><td class='num'>{s.point:g}</td>"
        f"<td class='num'>[{s.p10:g}, {s.p90:g}]</td></tr>"
        for i, s in enumerate(record.samples)
    )
    parts.append(
        "<h2>Samples</h2><table><thead><tr><th>#</th><th>point</th><th>80% interval</th></tr>"
        f"</thead><tbody>{srows}</tbody></table>"
    )
    prov = _dl(
        {
            "judge model": record.judge_model,
            "temperature": f"{record.temperature:g}",
            "n_samples": str(record.n_samples),
            "prompt_hash": record.prompt_hash,
            "inputs_hash": record.inputs_hash,
            "engine (git SHA)": record.engine_version,
            "cost": f"${record.cost_usd:.4f}",
        }
    )
    parts.append(
        '<div class="prov"><p><strong>This is a model judgment, not a computed forecast.</strong> '
        "It is non-deterministic: re-running produces different samples. The commitment is the "
        "SHA-256 of this record file (as <code>schelling seal</code> records).</p>"
        f"Provenance{prov}</div>"
    )
    return _page(f"LLM judgment — {record.question_id}", "".join(parts))


def _looks_like_draft(data: dict[str, Any]) -> bool:
    return {"game", "assumptions", "template_classification"} <= set(data)


def _looks_like_advise(data: dict[str, Any]) -> bool:
    return "advising_actor" in data and "own_moves" in data


def render(data: dict[str, Any], *, rubric_source: str | None = None) -> str:
    """Detect the artifact type and render it. Raises ValueError with a named reason otherwise.

    ``rubric_source`` (forecast records only) labels a rubric resolved from a grading file at render
    time so the appendix can state its origin (D24.1); None means the rubric was embedded.
    """
    if _looks_like_backtest(data):
        try:
            return render_backtest(BacktestRecord.model_validate(data))
        except ValidationError as exc:
            raise ValueError(
                f"this looks like a BacktestRecord but does not match the schema ({_fmt_err(exc)})."
            ) from exc
    if _looks_like_llm_forecast(data):
        try:
            return render_llm_forecast(LLMForecastRecord.model_validate(data))
        except ValidationError as exc:
            raise ValueError(
                f"this looks like an LLMForecastRecord but does not match the schema "
                f"({_fmt_err(exc)})."
            ) from exc
    if _looks_like_advise(data):
        try:
            return render_advise(AdviseRecord.model_validate(data))
        except ValidationError as exc:
            raise ValueError(
                f"this looks like an AdviseRecord but does not match the schema ({_fmt_err(exc)})."
            ) from exc
    if _looks_like_forecast(data):
        try:
            return render_forecast(ForecastRecord.model_validate(data), rubric_source=rubric_source)
        except ValidationError as exc:
            if "ensemble" not in data and "forecast_median" in data:
                raise ValueError(
                    "this is a ForecastRecord from an older schema (pre-`ensemble`, ~Session 3); "
                    "re-run `schelling solve` to regenerate it."
                ) from exc
            raise ValueError(
                f"this looks like a ForecastRecord but does not match the current schema "
                f"({_fmt_err(exc)}); re-run `schelling solve` to regenerate it."
            ) from exc
    if _looks_like_draft(data):
        try:
            return render_draft(DraftGameSpec.model_validate(data))
        except ValidationError as exc:
            raise ValueError(
                f"this looks like a DraftGameSpec but does not match the schema ({_fmt_err(exc)}); "
                "re-run `schelling formalize` to regenerate it."
            ) from exc
    raise ValueError("unrecognized artifact: expected a DraftGameSpec or a ForecastRecord JSON")
