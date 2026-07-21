"""Render Schelling artifacts to a single self-contained HTML report.

Accepts a ``DraftGameSpec`` (review sheet) or a ``ForecastRecord`` (full analysis). Output is
one HTML file with all CSS inlined, charts as inline SVG (no JS, no network), deterministic for
a given artifact (no wall-clock — CLAUDE.md rule 2). Opens offline and prints cleanly.
"""

from __future__ import annotations

import html
from typing import Any

from pydantic import ValidationError

from schelling.backtest.context import CITATIONS, CONTEXT_PROSE, PUBLISHED_RESULTS
from schelling.formalizer.schemas import DraftGameSpec, FetchedSource
from schelling.mc.sensitivity import zero_swing_warning
from schelling.report import svg
from schelling.report.svg import ActorPoint, BarRow, ScatterPoint, TornadoRow
from schelling.schemas.backtest import BacktestRecord
from schelling.schemas.forecast import (
    ADVISE_CAVEAT,
    AdviseRecord,
    AnalogPanel,
    Assumption,
    ForecastRecord,
    OwnMove,
    PersuasionTarget,
)
from schelling.schemas.question import GameSpec

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


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _rng(est: Any) -> str:
    return f"{est.low:g} / {est.mode:g} / {est.high:g}"


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


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head>"
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
        parts += ["<h2>Sources fetched — live web search</h2>", _sources_list(draft)]
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


def _sources_list(draft: DraftGameSpec) -> str:
    """A linked list of fetched sources with retrieval dates (data about the evidence, D8.2).

    Hyperlinks reference the source pages; the report loads no external resource on open, so it
    stays self-contained and offline (D8.4).
    """
    items: list[str] = []
    for s in _sorted_sources(draft.sources_fetched):
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


def render_forecast(record: ForecastRecord) -> str:
    """Render a ForecastRecord full-analysis report."""
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
    parts = [
        '<div class="kicker">Strategic advice — one-sided lever search</div>',
        f"<h1>{_esc(record.question_id)}</h1>",
        f'<p class="sub">advising <strong>{_esc(record.advising_actor)}</strong> · '
        f"ideal {record.ideal:g} · baseline settlement {record.baseline_median:.3f}</p>",
        f'<div class="caveat"><strong>Caveat.</strong> {_esc(ADVISE_CAVEAT)}</div>',
    ]
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
        _advise_provenance(record),
    ]
    return _page(record.question_id, "".join(parts))


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


def _looks_like_forecast(data: dict[str, Any]) -> bool:
    return "run_id" in data and any(
        k in data for k in ("ensemble", "forecast_median", "outcome_distribution")
    )


def _looks_like_draft(data: dict[str, Any]) -> bool:
    return {"game", "assumptions", "template_classification"} <= set(data)


def _looks_like_advise(data: dict[str, Any]) -> bool:
    return "advising_actor" in data and "own_moves" in data


def render(data: dict[str, Any]) -> str:
    """Detect the artifact type and render it. Raises ValueError with a named reason otherwise."""
    if _looks_like_backtest(data):
        try:
            return render_backtest(BacktestRecord.model_validate(data))
        except ValidationError as exc:
            raise ValueError(
                f"this looks like a BacktestRecord but does not match the schema ({_fmt_err(exc)})."
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
            return render_forecast(ForecastRecord.model_validate(data))
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
