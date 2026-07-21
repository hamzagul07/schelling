"""Render Schelling artifacts to a single self-contained HTML report.

Accepts a ``DraftGameSpec`` (review sheet) or a ``ForecastRecord`` (full analysis). Output is
one HTML file with all CSS inlined, charts as inline SVG (no JS, no network), deterministic for
a given artifact (no wall-clock — CLAUDE.md rule 2). Opens offline and prints cleanly.
"""

from __future__ import annotations

import html
from typing import Any

from pydantic import ValidationError

from schelling.formalizer.schemas import DraftGameSpec
from schelling.report import svg
from schelling.report.svg import ActorPoint, BarRow, ScatterPoint, TornadoRow
from schelling.schemas.forecast import (
    ADVISE_CAVEAT,
    AdviseRecord,
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
    parts = [
        '<div class="kicker">Draft game specification — for review</div>',
        f"<h1>{_esc(g.question_id)}</h1>",
        f'<p class="sub">frozen {_esc(g.frozen_at)} · template: {_esc(tc.template)} · '
        f"horizon: {_esc(g.horizon)}</p>",
        f'<p class="sub"><strong>{_esc(g.continuum.label)}</strong><br>'
        f"0 = {_esc(g.continuum.anchor_0)} &nbsp;·&nbsp; 100 = {_esc(g.continuum.anchor_100)}</p>",
        "<h2>Actor map</h2>",
        f"<figure>{svg.actor_map(_actor_points(g))}</figure>",
        "<h2>Stakeholders</h2>",
        _actor_table(g, with_evidence=True),
        "<h2>Open assumptions — review before solving</h2>",
        _assumptions(draft),
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
        '<div class="kicker">Forecast analysis</div>',
        f"<h1>{_esc(record.question_id)}</h1>",
        f'<p class="sub">frozen {_esc(frozen)} · template: {_esc(template)}</p>',
        f'<p class="sub">run {_esc(record.run_id)}</p>',
        "<h2>Headline</h2>",
        '<div class="metrics">'
        + _metric(f"{e.median:.3f}", "settlement median")
        + _metric(f"[{e.p10:.2f}, {e.p90:.2f}]", "CI80")
        + _metric(f"{e.mean:.3f}", "expected (mean)")
        + _metric(f"{cv.get('converged_fraction', 0.0) * 100:.0f}%", "converged")
        + _metric(f"{cv.get('rounds_mean', 0.0):.1f}", "mean rounds")
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
    parts.append(_forecast_provenance(record))
    return _page(record.question_id, "".join(parts))


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
        f"<td class='num'>{t.from_value:g} &rarr; {t.to_value:g}</td>"
        f"<td class='num'>{t.settlement_median:.3f}</td><td class='num'>{t.benefit:+.3f}</td></tr>"
        for t in targets
    )
    return (
        "<table><thead><tr><th>actor</th><th>lever</th><th>shift</th><th>settlement</th>"
        f"<th>benefit</th></tr></thead><tbody>{rows}</tbody></table>"
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
    bars = [BarRow(f"{t.actor_id}.{t.dimension}", t.benefit) for t in record.persuasion_targets[:8]]
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
