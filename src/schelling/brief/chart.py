"""The brief's continuum chart — a generated, deterministic inline SVG (Session 56, D56).

Every mark is positioned from a forecast's value on the question's 0-100 continuum; the reality rule
is the graded value; each model family's thin -> researched pair is joined by a dashed line. The
axis bounds are SCALED to the spread of the plotted values (a nice-number range around them), never
hardcoded, so a different question's brief picks its own sensible scale. No script, no external ref,
integer-precision coordinates -> byte-identical on re-run. ``role="img"`` with a generated title and
desc; colours are CSS custom properties, so the chart stays legible in light and dark.
"""

from __future__ import annotations

import math

from schelling.brief.data import BriefData, RecordFig
from schelling.report.svg import _n

# Chart frame (viewBox 0 0 1180 300). The data band maps [lo, hi] onto [PLOT_X0, PLOT_X1]; the axis
# rule runs a little past it to AXIS_X1 (matching the approved reference proportions).
_VIEW_W, _VIEW_H = 1180, 300
_PLOT_X0, _PLOT_X1, _AXIS_X1 = 90.0, 1100.0, 1140.0
_LABEL_X = 78.0  # right-aligned family labels sit left of the data band
_TOP_Y, _ROW_GAP = 71.0, 55.0
_AXIS_Y, _TICK_Y, _SCALE_Y = 248.0, 268.0, 288.0
_RULE_Y1, _RULE_Y2, _RULE_LABEL_Y = 34.0, 232.0, 24.0
_R_THIN, _R_RESEARCHED = 5.0, 6.5
_THIN_ANNOT_GAP = 180.0  # only annotate a thin mark on its left when its pair is this far right

_FAMILY_ORDER = ("challenge", "compromise", "llm")
_CHART_LABEL = {"challenge": "challenge", "compromise": "compromise", "llm": "AI judgement"}


def _nice_axis(vmin: float, vmax: float) -> tuple[float, float, list[float]]:
    """A padded, round-numbered axis around ``[vmin, vmax]`` — (lo, hi, ticks).

    Pads the spread by 10% each side, then snaps to a 1/2/2.5/5 x 10^k step targeting ~5 intervals,
    so the bounds are round and the marks never sit on the edge. Pure and deterministic.
    """
    span = (vmax - vmin) or 1.0
    pad = span * 0.10
    lo_raw, hi_raw = vmin - pad, vmax + pad
    raw_step = (hi_raw - lo_raw) / 5.0
    magnitude = 10.0 ** math.floor(math.log10(raw_step))
    step = magnitude
    for mult in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = mult * magnitude
        if step >= raw_step:
            break
    lo = math.floor(lo_raw / step) * step
    hi = math.ceil(hi_raw / step) * step
    ticks: list[float] = []
    t = lo
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 6))
        t += step
    return lo, hi, ticks


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_chart(data: BriefData) -> str:
    """The inline ``<svg>`` chart for a brief — a pure function of ``data`` (byte-identical)."""
    plotted = [r.median for r in data.records] + [data.actual_continuum]
    lo, hi, ticks = _nice_axis(min(plotted), max(plotted))
    span = hi - lo

    def x(value: float) -> float:
        return _PLOT_X0 + (value - lo) / span * (_PLOT_X1 - _PLOT_X0)

    best = data.best_record
    parts: list[str] = []

    # reality rule — the graded value
    x_real = x(data.actual_continuum)
    parts.append(
        f'<line x1="{_n(x_real)}" y1="{_n(_RULE_Y1)}" x2="{_n(x_real)}" y2="{_n(_RULE_Y2)}" '
        f'stroke="var(--real)" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{_n(x_real)}" y="{_n(_RULE_LABEL_Y)}" text-anchor="middle" '
        f'font-family="Georgia,serif" font-size="15" fill="var(--real)">'
        f"reality — {data.actual_continuum:g}</text>"
    )

    # faint gridlines at each tick (the instrument graticule), behind the marks
    grid = "".join(
        f'<line x1="{_n(x(t))}" y1="{_n(_RULE_Y1)}" x2="{_n(x(t))}" y2="{_n(_AXIS_Y)}"/>'
        for t in ticks
    )
    parts.insert(0, f'<g stroke="var(--rule-3)" stroke-width="1">{grid}</g>')

    # axis rule + ticks + scale caption
    parts.append(
        f'<line x1="{_n(_PLOT_X0)}" y1="{_n(_AXIS_Y)}" x2="{_n(_AXIS_X1)}" y2="{_n(_AXIS_Y)}" '
        f'stroke="var(--rule-2)" stroke-width="1"/>'
    )
    ticks_svg = "".join(
        f'<text x="{_n(x(t))}" y="{_n(_TICK_Y)}" text-anchor="middle">{t:g}</text>' for t in ticks
    )
    parts.append(
        '<g font-family="ui-monospace,Menlo,monospace" font-size="11" fill="var(--ink-3)" '
        f'text-anchor="middle">{ticks_svg}'
        f'<text x="{_n(_PLOT_X0)}" y="{_n(_SCALE_Y)}" text-anchor="start">'
        "rollover ← · outcome scale · → bigger increase</text></g>"
    )

    # one row per model family: thin -> researched pair, joined
    by_family: dict[str, dict[str, RecordFig]] = {}
    for r in data.records:
        by_family.setdefault(r.family, {})[r.vintage] = r
    for i, fam in enumerate(_FAMILY_ORDER):
        pair = by_family.get(fam)
        if not pair:
            continue
        y = _TOP_Y + i * _ROW_GAP
        thin, res = pair.get("v1-thin"), pair.get("v2-sourced")
        parts.append(
            f'<text x="{_n(_LABEL_X)}" y="{_n(y + 5)}" text-anchor="end" font-size="14" '
            f'fill="var(--ink-2)">{_esc(_CHART_LABEL[fam])}</text>'
        )
        if thin and res:
            parts.append(
                f'<line x1="{_n(x(thin.median))}" y1="{_n(y)}" x2="{_n(x(res.median))}" '
                f'y2="{_n(y)}" stroke="var(--graphite)" stroke-width="1.5" '
                f'stroke-dasharray="3 3" opacity=".55"/>'
            )
        if thin:
            parts.append(
                f'<circle cx="{_n(x(thin.median))}" cy="{_n(y)}" r="{_n(_R_THIN)}" fill="none" '
                f'stroke="var(--graphite)" stroke-width="1.5"/>'
            )
        if res:
            fill = "var(--real)" if res is best else "var(--graphite)"
            parts.append(
                f'<circle cx="{_n(x(res.median))}" cy="{_n(y)}" r="{_n(_R_RESEARCHED)}" '
                f'fill="{fill}"/>'
            )
            annot = "exact" if res.error < 0.05 else f"off by {res.error:.1f}"
            colour = "var(--real)" if res is best else "var(--ink-3)"
            parts.append(
                f'<text x="{_n(x(res.median) + 15)}" y="{_n(y + 5)}" '
                f'font-family="ui-monospace,Menlo,monospace" font-size="12" fill="{colour}">'
                f"{annot}</text>"
            )
        # annotate the thin mark on its left only when the pair is far enough apart to have room
        if thin and res and x(res.median) - x(thin.median) >= _THIN_ANNOT_GAP:
            parts.append(
                f'<text x="{_n(x(thin.median) - 15)}" y="{_n(y + 5)}" text-anchor="end" '
                f'font-family="ui-monospace,Menlo,monospace" font-size="12" fill="var(--ink-3)">'
                f"off by {thin.error:.1f}</text>"
            )

    # legend
    parts.append(
        '<g transform="translate(90,218)">'
        '<circle cx="6" cy="-4" r="5" fill="none" stroke="var(--graphite)" stroke-width="1.5"/>'
        '<text x="20" y="0" font-size="12.5" fill="var(--ink-3)">thin evidence</text>'
        '<circle cx="146" cy="-4" r="6.5" fill="var(--graphite)"/>'
        '<text x="160" y="0" font-size="12.5" fill="var(--ink-3)">after deep research</text></g>'
    )

    title = f"Sealed forecasts against the actual outcome of {data.actual_continuum:g}"
    desc = (
        f"{len(data.records)} sealed forecasts on a {lo:g} to {hi:g} outcome scale; the closest, "
        f"{best.method_label} on {best.evidence_label} evidence, landed at {best.median:g} "
        f"(off by {best.error:g}); reality fell at {data.actual_continuum:g}."
    )
    return (
        f'<svg viewBox="0 0 {_VIEW_W} {_VIEW_H}" width="100%" role="img" '
        f'aria-label="{_esc(title)}"><title>{_esc(title)}</title><desc>{_esc(desc)}</desc>'
        + "".join(parts)
        + "</svg>"
    )
