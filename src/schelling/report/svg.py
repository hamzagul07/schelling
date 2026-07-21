"""Deterministic inline-SVG chart primitives for reports (no JS, no network).

Every function returns an SVG string with numeric coordinates formatted to a fixed precision,
so the same inputs render byte-identical output (CLAUDE.md rule 2). Styling is by CSS class —
colors live in the report stylesheet, keeping the palette centralized and restrained.
"""

from __future__ import annotations

import html
import math
from collections.abc import Sequence
from typing import NamedTuple


class ActorPoint(NamedTuple):
    """One plotted actor: low-mode-high range plus a size weight (capability x salience)."""

    name: str
    low: float
    mode: float
    high: float
    weight: float


def _n(v: float) -> str:
    """Format a coordinate deterministically (trim -0.00)."""
    s = f"{v:.2f}"
    return "0.00" if s == "-0.00" else s


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _nice_bounds(lo: float, hi: float, pad_frac: float = 0.05) -> tuple[float, float]:
    """A padded [lo, hi] that never collapses to a point."""
    if hi <= lo:
        return lo - 1.0, hi + 1.0
    pad = (hi - lo) * pad_frac
    return lo - pad, hi + pad


def _svg(width: float, height: float, body: str) -> str:
    # No xmlns: inline SVG in an HTML5 document is placed in the SVG namespace by the parser.
    # Omitting it keeps the report free of any URL-shaped strings (offline-clean).
    return (
        f'<svg viewBox="0 0 {_n(width)} {_n(height)}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img">'
        f"{body}</svg>"
    )


def _line(x1: float, y1: float, x2: float, y2: float, cls: str) -> str:
    return f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" class="{cls}"/>'


def _text(x: float, y: float, s: str, cls: str, anchor: str = "start") -> str:
    return f'<text x="{_n(x)}" y="{_n(y)}" text-anchor="{anchor}" class="{cls}">{_esc(s)}</text>'


def _axis_ticks(x0: float, x1: float, y: float, dmin: float, dmax: float) -> str:
    """Numeric axis with three ticks (min, mid, max)."""
    parts = [_line(x0, y, x1, y, "axis")]
    for frac in (0.0, 0.5, 1.0):
        px = x0 + (x1 - x0) * frac
        val = dmin + (dmax - dmin) * frac
        parts.append(_line(px, y, px, y + 4, "axis"))
        anchor = "start" if frac == 0.0 else "end" if frac == 1.0 else "middle"
        parts.append(_text(px, y + 16, f"{val:g}", "tick", anchor))
    return "".join(parts)


def actor_map(
    actors: Sequence[ActorPoint], *, settlement: float | None = None, width: float = 680.0
) -> str:
    """Actors as dots on the issue line: whiskers = low-high, dot area ~ capability x salience."""
    if not actors:
        return _svg(width, 40, _text(width / 2, 24, "(no actors)", "tick", "middle"))

    label_w = 172.0
    x0, x1 = label_w + 8.0, width - 20.0
    row_h = 30.0
    top = 16.0
    axis_y = top + len(actors) * row_h + 10.0
    height = axis_y + 28.0

    lows = [a.low for a in actors] + ([settlement] if settlement is not None else [])
    highs = [a.high for a in actors] + ([settlement] if settlement is not None else [])
    dmin, dmax = _nice_bounds(min(lows), max(highs))

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * (v - dmin) / (dmax - dmin)

    max_w = max((a.weight for a in actors), default=1.0) or 1.0
    parts: list[str] = []

    if settlement is not None:
        px = sx(settlement)
        parts.append(_line(px, top - 4, px, axis_y, "settle-line"))
        parts.append(_text(px, top - 8, f"settlement {settlement:g}", "settle-label", "middle"))

    for i, a in enumerate(actors):
        y = top + i * row_h + row_h / 2
        parts.append(_text(label_w, y + 4, a.name, "actor-label", "end"))
        parts.append(_line(sx(a.low), y, sx(a.high), y, "whisker"))
        for end in (a.low, a.high):
            parts.append(_line(sx(end), y - 3, sx(end), y + 3, "whisker"))
        r = 4.0 + 9.0 * math.sqrt(max(a.weight, 0.0) / max_w)
        parts.append(f'<circle cx="{_n(sx(a.mode))}" cy="{_n(y)}" r="{_n(r)}" class="dot"/>')

    parts.append(_axis_ticks(x0, x1, axis_y, dmin, dmax))
    return _svg(width, height, "".join(parts))


def histogram(
    values: Sequence[float],
    *,
    p10: float,
    p90: float,
    median: float,
    width: float = 680.0,
    height: float = 200.0,
    bins: int = 24,
) -> str:
    """Outcome-distribution histogram with a CI80 band and a median line."""
    if not values:
        return _svg(width, 40, _text(width / 2, 24, "(no draws)", "tick", "middle"))
    x0, x1 = 20.0, width - 20.0
    y0, y1 = 12.0, height - 26.0
    dmin, dmax = min(values), max(values)
    if dmax <= dmin:
        dmin, dmax = dmin - 0.5, dmax + 0.5

    counts = [0] * bins
    span = dmax - dmin
    for v in values:
        idx = min(bins - 1, int((v - dmin) / span * bins))
        counts[idx] += 1
    peak = max(counts) or 1

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * (v - dmin) / span

    parts: list[str] = []
    # CI80 band behind the bars.
    parts.append(
        f'<rect x="{_n(sx(p10))}" y="{_n(y0)}" width="{_n(sx(p90) - sx(p10))}" '
        f'height="{_n(y1 - y0)}" class="ci-band"/>'
    )
    bw = (x1 - x0) / bins
    for i, c in enumerate(counts):
        if c == 0:
            continue
        bh = (y1 - y0) * c / peak
        bx = x0 + i * bw
        parts.append(
            f'<rect x="{_n(bx + 0.5)}" y="{_n(y1 - bh)}" width="{_n(bw - 1.0)}" '
            f'height="{_n(bh)}" class="bar"/>'
        )
    parts.append(_line(sx(median), y0, sx(median), y1, "median-line"))
    parts.append(_line(x0, y1, x1, y1, "axis"))
    for frac, anchor in ((0.0, "start"), (1.0, "end")):
        val = dmin + span * frac
        parts.append(_text(x0 + (x1 - x0) * frac, y1 + 16, f"{val:g}", "tick", anchor))
    parts.append(_text((x0 + x1) / 2, y1 + 16, f"median {median:g}", "tick", "middle"))
    return _svg(width, height, "".join(parts))


class TornadoRow(NamedTuple):
    label: str
    f_low: float
    f_high: float
    swing: float


def tornado(rows: Sequence[TornadoRow], *, baseline: float, width: float = 680.0) -> str:
    """Sensitivity tornado: a horizontal bar per parameter, from forecast-at-low to -at-high."""
    if not rows:
        note = _text(width / 2, 24, "no ranged parameters (point estimates)", "tick", "middle")
        return _svg(width, 40, note)
    label_w = 172.0
    x0, x1 = label_w + 8.0, width - 60.0
    row_h = 30.0
    top = 12.0
    height = top + len(rows) * row_h + 24.0

    vals = [baseline]
    for r in rows:
        vals += [r.f_low, r.f_high]
    dmin, dmax = _nice_bounds(min(vals), max(vals))

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * (v - dmin) / (dmax - dmin)

    parts = [_line(sx(baseline), top - 2, sx(baseline), top + len(rows) * row_h, "baseline")]
    for i, r in enumerate(rows):
        y = top + i * row_h + row_h / 2
        lo, hi = sorted((r.f_low, r.f_high))
        parts.append(_text(label_w, y + 4, r.label, "actor-label", "end"))
        parts.append(
            f'<rect x="{_n(sx(lo))}" y="{_n(y - 7)}" width="{_n(max(sx(hi) - sx(lo), 1.0))}" '
            f'height="14" class="tbar"/>'
        )
        parts.append(_text(x1 + 6, y + 4, f"{r.swing:+.2f}", "swing", "start"))
    return _svg(width, height, "".join(parts))


class ScatterPoint(NamedTuple):
    x: float
    y: float
    label: str


def scatter(
    points: Sequence[ScatterPoint],
    *,
    x_label: str = "",
    y_label: str = "",
    width: float = 680.0,
    height: float = 260.0,
) -> str:
    """A scatter with a y=0 reference line — for own-move benefit (y) vs cost conceded (x)."""
    if not points:
        return _svg(width, 40, _text(width / 2, 24, "(no moves)", "tick", "middle"))
    x0, x1 = 46.0, width - 20.0
    y0, y1 = 16.0, height - 34.0
    xs = [p.x for p in points] + [0.0]
    ys = [p.y for p in points] + [0.0]
    xmin, xmax = _nice_bounds(min(xs), max(xs))
    ymin, ymax = _nice_bounds(min(ys), max(ys))

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * (v - xmin) / (xmax - xmin)

    def sy(v: float) -> float:
        return y1 - (y1 - y0) * (v - ymin) / (ymax - ymin)

    parts = [_line(x0, sy(0.0), x1, sy(0.0), "baseline"), _line(x0, y0, x0, y1, "axis")]
    for p in points:
        parts.append(f'<circle cx="{_n(sx(p.x))}" cy="{_n(sy(p.y))}" r="3.5" class="dot"/>')
    parts.append(_text(x0, y1 + 16, f"{x_label} {xmin:g}", "tick", "start"))
    parts.append(_text(x1, y1 + 16, f"{xmax:g}", "tick", "end"))
    parts.append(_text(x0 - 6, sy(ymax) + 4, f"{ymax:g}", "tick", "end"))
    parts.append(_text(x0 - 6, sy(ymin) + 4, f"{ymin:g}", "tick", "end"))
    parts.append(_text(x0 - 6, y0 - 4, y_label, "tick", "end"))
    return _svg(width, height, "".join(parts))


class BarRow(NamedTuple):
    label: str
    value: float


def hbars(rows: Sequence[BarRow], *, width: float = 680.0) -> str:
    """Horizontal bars from a zero baseline (signed) — for the persuasion-target ranking."""
    if not rows:
        return _svg(width, 40, _text(width / 2, 24, "(no targets)", "tick", "middle"))
    label_w = 190.0
    x0, x1 = label_w + 8.0, width - 54.0
    row_h = 26.0
    top = 10.0
    height = top + len(rows) * row_h + 12.0
    vals = [r.value for r in rows] + [0.0]
    dmin, dmax = _nice_bounds(min(vals), max(vals))

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * (v - dmin) / (dmax - dmin)

    zero = sx(0.0)
    parts = [_line(zero, top - 2, zero, top + len(rows) * row_h, "baseline")]
    for i, r in enumerate(rows):
        y = top + i * row_h + row_h / 2
        bx = min(zero, sx(r.value))
        bw = max(abs(sx(r.value) - zero), 1.0)
        parts.append(_text(label_w, y + 4, r.label, "actor-label", "end"))
        parts.append(
            f'<rect x="{_n(bx)}" y="{_n(y - 7)}" width="{_n(bw)}" height="14" class="tbar"/>'
        )
        parts.append(_text(x1 + 6, y + 4, f"{r.value:+.2f}", "swing", "start"))
    return _svg(width, height, "".join(parts))


def trajectory(medians: Sequence[float], *, width: float = 680.0, height: float = 190.0) -> str:
    """Per-round median trajectory as a line with round markers."""
    if not medians:
        return _svg(width, 40, _text(width / 2, 24, "(no rounds)", "tick", "middle"))
    x0, x1 = 34.0, width - 20.0
    y0, y1 = 14.0, height - 26.0
    n = len(medians)
    dmin, dmax = _nice_bounds(min(medians), max(medians), 0.1)

    def sx(i: int) -> float:
        return x0 if n == 1 else x0 + (x1 - x0) * i / (n - 1)

    def sy(v: float) -> float:
        return y1 - (y1 - y0) * (v - dmin) / (dmax - dmin)

    parts = [_line(x0, y1, x1, y1, "axis")]
    parts.append(_text(x0 - 6, sy(dmax) + 4, f"{dmax:g}", "tick", "end"))
    parts.append(_text(x0 - 6, sy(dmin) + 4, f"{dmin:g}", "tick", "end"))
    if n > 1:
        pts = " ".join(f"{_n(sx(i))},{_n(sy(m))}" for i, m in enumerate(medians))
        parts.append(f'<polyline points="{pts}" class="traj-line"/>')
    for i, m in enumerate(medians):
        parts.append(f'<circle cx="{_n(sx(i))}" cy="{_n(sy(m))}" r="3" class="dot"/>')
        parts.append(_text(sx(i), y1 + 16, str(i + 1), "tick", "middle"))
    return _svg(width, height, "".join(parts))
