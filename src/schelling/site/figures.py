"""The instrument layer: two deterministic inline-SVG figures (Session 34; rescaled full-bleed to a
1200-unit viewBox in Session 35, D35.3).

Both are pure functions of committed artifacts — the sealed ledger and its interval snapshot, the
rubric bands, the evidence table and the successor leaderboard — so they regenerate byte-for-byte
and survive ``site build --check``. No coordinate is hand-plotted: every mark is positioned from a
sourced value. Data marks are coloured by model family from the report renderer's palette (challenge
amber, compromise teal, llm-judgment grey); structural strokes, rules and labels use the site's CSS
variables so they stay legible in dark mode. Each figure is ``role="img"`` with a generated title
and desc, and renders full-bleed at the content width.
"""

from __future__ import annotations

import math

from schelling.report.palette import load_palette
from schelling.report.svg import Palette, _n, _svg, _text
from schelling.site.data import LedgerRow, SiteData, trial_gates

_W = 1200.0


def _rect(
    x: float, y: float, w: float, h: float, *, fill: str = "", cls: str = "", op: float = 1.0
) -> str:
    a = f' fill="{fill}"' if fill else ""
    a += f' class="{cls}"' if cls else ""
    a += f' opacity="{_n(op)}"' if op < 1.0 else ""
    return f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(max(w, 0.0))}" height="{_n(h)}"{a}/>'


def _circle(cx: float, cy: float, r: float, fill: str) -> str:
    return f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="{fill}"/>'


def _vline(x: float, y1: float, y2: float, cls: str) -> str:
    return f'<line x1="{_n(x)}" y1="{_n(y1)}" x2="{_n(x)}" y2="{_n(y2)}" class="{cls}"/>'


def _hline(x1: float, x2: float, y: float, cls: str) -> str:
    return f'<line x1="{_n(x1)}" y1="{_n(y)}" x2="{_n(x2)}" y2="{_n(y)}" class="{cls}"/>'


def _short(label: str, n: int) -> str:
    label = label.strip()
    return label if len(label) <= n else label[: n - 1].rstrip() + "…"


def _model_colour(model: str, pal: Palette) -> str:
    """Fixed colour per model family, all from the report palette (D35.3)."""
    if model.startswith("challenge"):
        return pal.low_half
    if model.startswith("compromise"):
        return pal.high_half
    return pal.ci_bracket


def _band_index(value: float, bands_lo: list[float]) -> int:
    """Index of the band ``value`` falls in — the last band whose ``lo`` it clears (clamped)."""
    idx = 0
    for i, lo in enumerate(bands_lo):
        if value >= lo:
            idx = i
    return idx


# --------------------------------------------------------------------------- figure 1: landscape
def forecast_landscape(data: SiteData) -> str:
    """One group per sealed question, one row per model forecast: the median as a dot and the 80%
    interval as a bar on the question's 0-100 continuum, coloured by model family, with the rubric
    band boundaries drawn behind as thin rules and the modal band (the one holding the most medians)
    tinted and labelled. Resolution date at the right of each group, a legend above."""
    pal = load_palette()
    order: list[str] = []
    bucket: dict[str, list[LedgerRow]] = {}
    for row in data.ledger:
        bucket.setdefault(row.question, []).append(row)
        if row.question not in order:
            order.append(row.question)
    if not order:
        return ""

    x0, x1, val_x, edge = 44.0, 940.0, 958.0, 1190.0
    span = x1 - x0

    def sx(v: float) -> float:
        return x0 + span * max(0.0, min(100.0, v)) / 100.0

    rh, gh, ggap, legend_h, axis_h, pad = 26.0, 30.0, 22.0, 34.0, 30.0, 12.0
    height = pad + legend_h
    for qid in order:
        height += gh + rh * len(bucket[qid]) + ggap
    height += axis_h

    body: list[str] = []
    # legend: the model families present, each with its colour, then the bar meaning at the right
    seen: list[str] = []
    for r in data.ledger:
        if r.model not in seen:
            seen.append(r.model)
    lx = x0
    ly = pad + 16.0
    for model in seen:
        body.append(_circle(lx + 5.0, ly - 4.0, 5.0, _model_colour(model, pal)))
        body.append(_text(lx + 16.0, ly, model, "fig-legend"))
        lx += 40.0 + len(model) * 8.0
    body.append(_text(edge, ly, "bar = 80% of simulated worlds", "fig-legend", "end"))

    y = pad + legend_h
    for qid in order:
        rows = bucket[qid]
        bands = data.rubric_bands.get(qid, [])
        bands_lo = [b.lo for b in bands]
        medians = [float(r.median) for r in rows]
        rows_top = y + gh - 8.0
        rows_bot = y + gh + rh * len(rows)

        if bands:
            counts = [0] * len(bands)
            for m in medians:
                counts[_band_index(m, bands_lo)] += 1
            modal = max(range(len(bands)), key=lambda i: (counts[i], -i))
            m_lo = sx(bands[modal].lo)
            m_hi = sx(bands_lo[modal + 1]) if modal + 1 < len(bands) else sx(100.0)
            body.append(_rect(m_lo, rows_top, m_hi - m_lo, rows_bot - rows_top, cls="fig-modal"))
            for b in bands:
                if b.lo > 0.0:
                    body.append(_vline(sx(b.lo), rows_top, rows_bot, "fig-rule"))
            body.append(
                _text(
                    (m_lo + m_hi) / 2.0,
                    y + 16.0,
                    _short(bands[modal].label, 34),
                    "fig-modal-lab",
                    "middle",
                )
            )

        info = data.questions.get(qid)
        body.append(_text(0.0, y + 16.0, qid, "fig-title"))
        if info and info.resolution_date:
            body.append(_text(edge, y + 16.0, f"resolves {info.resolution_date}", "fig-num", "end"))

        for i, r in enumerate(rows):
            cy = y + gh + rh * i + rh / 2.0
            colour = _model_colour(r.model, pal)
            iv = data.intervals.get(r.sha256)
            if iv is not None:
                lo, hi = sx(iv[0]), sx(iv[1])
                body.append(_rect(lo, cy - 3.0, hi - lo, 6.0, fill=colour, op=0.4))
            body.append(_circle(sx(float(r.median)), cy, 5.0, colour))
            body.append(_text(val_x, cy + 4.0, f"{r.median} · {r.model}", "fig-num"))
        y = rows_bot + ggap

    ay = height - axis_h + 8.0
    body.append(_hline(x0, x1, ay, "fig-axis"))
    for v in (0.0, 50.0, 100.0):
        body.append(_vline(sx(v), ay, ay + 5.0, "fig-axis"))
        anchor = "start" if v == 0.0 else "end" if v == 100.0 else "middle"
        body.append(_text(sx(v), ay + 20.0, f"{v:g}", "fig-tick", anchor))
    body.append(
        _text((x0 + x1) / 2.0, height - 2.0, "settlement continuum (0-100)", "fig-tick", "middle")
    )

    n_rows = sum(len(bucket[q]) for q in order)
    desc = (
        f"{len(order)} sealed questions and {n_rows} model forecasts, each plotted as a median dot "
        "and 80% interval bar on its 0-100 continuum, coloured by model family, with rubric band "
        "boundaries behind and the modal band labelled."
    )
    return _svg(_W, height, "".join(body), title="The forecast landscape", desc=desc)


# --------------------------------------------------------------------------- figure 2: the trials
def trials(data: SiteData) -> str:
    """A horizontal bar pair per pre-registered gate — the model's MAE against the baseline's on a
    shared scale, verdict as a monospace label — ordered as the tests ran, so it reads as a sequence
    of attempts. Sourced from the backtest via :func:`trial_gates`."""
    pal = load_palette()
    rows = trial_gates(data)
    if not rows:
        return ""
    x0, x1, val_x, edge = 360.0, 840.0, 858.0, 1190.0
    top = max(5.0, math.ceil(max(max(m, b) for _, m, b, _ in rows) / 5.0) * 5.0)

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * v / top

    pad, legend_h, block, axis_h = 12.0, 30.0, 52.0, 30.0
    height = pad + legend_h + block * len(rows) + axis_h

    body: list[str] = []
    ly = pad + 16.0
    body.append(_rect(x0, ly - 8.0, 22.0, 5.0, fill=pal.low_half))
    body.append(_text(x0 + 30.0, ly, "model", "fig-legend"))
    body.append(_rect(x0 + 96.0, ly - 8.0, 22.0, 5.0, fill=pal.ci_bracket))
    body.append(_text(x0 + 126.0, ly, "baseline", "fig-legend"))

    y = pad + legend_h
    for label, model_mae, base_mae, verdict in rows:
        body.append(_text(0.0, y + 24.0, label, "fig-title"))
        body.append(_rect(x0, y + 12.0, sx(model_mae) - x0, 12.0, fill=pal.low_half, op=0.9))
        body.append(_rect(x0, y + 28.0, sx(base_mae) - x0, 12.0, fill=pal.ci_bracket, op=0.7))
        body.append(_text(val_x, y + 30.0, f"{model_mae:g} / {base_mae:g}", "fig-num"))
        vcol = pal.high_half if verdict == "ceiling" else pal.low_half
        body.append(
            f'<text x="{_n(edge)}" y="{_n(y + 30.0)}" text-anchor="end" '
            f'class="fig-verdict" fill="{vcol}">{verdict}</text>'
        )
        y += block

    ay = height - axis_h + 8.0
    body.append(_hline(x0, x1, ay, "fig-axis"))
    for frac in (0.0, 0.5, 1.0):
        v = top * frac
        px = sx(v)
        body.append(_vline(px, ay, ay + 5.0, "fig-axis"))
        anchor = "start" if frac == 0.0 else "end" if frac == 1.0 else "middle"
        body.append(_text(px, ay + 20.0, f"{v:g}", "fig-tick", anchor))
    body.append(
        _text(
            (x0 + x1) / 2.0, height - 2.0, "mean absolute error (0-100 scale)", "fig-tick", "middle"
        )
    )

    desc = (
        f"{len(rows)} pre-registered gates in the order they ran; each shows the model's mean "
        "absolute error against the baseline's on a shared scale, with the verdict."
    )
    return _svg(_W, height, "".join(body), title="The trials", desc=desc)
