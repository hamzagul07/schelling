"""The instrument layer: two deterministic inline-SVG figures (Session 34, D34).

Both are pure functions of committed artifacts — the sealed ledger and its interval snapshot, the
rubric bands, the evidence table and the successor leaderboard — so they regenerate byte-for-byte
and survive ``site build --check``. No coordinate is hand-plotted: every mark's position is computed
from a sourced value. Data marks reuse the report renderer's palette (amber for the 0-end half, teal
for the 100-end half); structural strokes, rules, and labels use the site's CSS variables so the
figures stay legible in dark mode. Each figure is ``role="img"`` with a generated title and desc.
"""

from __future__ import annotations

import math
import re

from schelling.report.palette import load_palette
from schelling.report.svg import Palette, _n, _svg, _text
from schelling.site.data import LedgerRow, SiteData

_W = 680.0


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


def _half(mid: float, pal: Palette) -> str:
    """The continuum-half colour for a mark at ``mid`` (amber below 50, teal at/above)."""
    return pal.low_half if mid < 50.0 else pal.high_half


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
    interval as a bar on the question's 0-100 continuum, with the rubric band boundaries drawn
    behind as thin rules and the modal band (the one holding the most medians) labelled."""
    pal = load_palette()
    order: list[str] = []
    bucket: dict[str, list[LedgerRow]] = {}
    for row in data.ledger:
        bucket.setdefault(row.question, []).append(row)
        if row.question not in order:
            order.append(row.question)
    if not order:
        return ""

    left, right = 130.0, 92.0
    x0, x1 = left, _W - right
    span = x1 - x0

    def sx(v: float) -> float:
        return x0 + span * max(0.0, min(100.0, v)) / 100.0

    rh, gh, ggap, legend_h, axis_h, pad = 20.0, 24.0, 18.0, 28.0, 26.0, 10.0
    height = pad + legend_h
    for qid in order:
        height += gh + rh * len(bucket[qid]) + ggap
    height += axis_h

    body: list[str] = []
    # legend
    ly = pad + 14.0
    body.append(_circle(x0 + 4.0, ly - 4.0, 3.5, pal.low_half))
    body.append(_text(x0 + 14.0, ly, "median", "fig-legend"))
    body.append(_rect(x0 + 74.0, ly - 6.5, 30.0, 4.0, fill=pal.low_half, op=0.34))
    body.append(_text(x0 + 110.0, ly, "80% interval", "fig-legend"))

    y = pad + legend_h
    for qid in order:
        rows = bucket[qid]
        bands = data.rubric_bands.get(qid, [])
        bands_lo = [b.lo for b in bands]
        medians = [float(r.median) for r in rows]
        rows_top = y + gh - 6.0
        rows_bot = y + gh + rh * len(rows)

        # modal band = the band holding the most model medians (ties resolve to the lower band)
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
                    y + 12.0,
                    _short(bands[modal].label, 26),
                    "fig-modal-lab",
                    "middle",
                )
            )

        # group header: question id (mono) left, resolution date (mono) right
        info = data.questions.get(qid)
        body.append(_text(4.0, y + 12.0, qid, "fig-id"))
        if info and info.resolution_date:
            body.append(_text(x1, y + 12.0, info.resolution_date, "fig-num", "end"))

        for i, r in enumerate(rows):
            cy = y + gh + rh * i + rh / 2.0
            colour = _half(float(r.median), pal)
            body.append(_text(x0 - 8.0, cy + 3.5, f"{r.model} {r.vintage}", "fig-lab", "end"))
            iv = data.intervals.get(r.sha256)
            if iv is not None:
                lo, hi = sx(iv[0]), sx(iv[1])
                body.append(_rect(lo, cy - 2.5, hi - lo, 5.0, fill=colour, op=0.34))
            body.append(_circle(sx(float(r.median)), cy, 3.5, colour))
        y = rows_bot + ggap

    # shared continuum axis
    ay = height - axis_h + 6.0
    body.append(_hline(x0, x1, ay, "fig-axis"))
    for v in (0.0, 50.0, 100.0):
        body.append(_vline(sx(v), ay, ay + 4.0, "fig-axis"))
        anchor = "start" if v == 0.0 else "end" if v == 100.0 else "middle"
        body.append(_text(sx(v), ay + 16.0, f"{v:g}", "fig-tick", anchor))
    body.append(
        _text((x0 + x1) / 2.0, height - 2.0, "settlement continuum (0-100)", "fig-tick", "middle")
    )

    n_rows = sum(len(bucket[q]) for q in order)
    title = "The forecast landscape"
    desc = (
        f"{len(order)} sealed questions and {n_rows} model forecasts, each plotted as a median dot "
        "and 80% interval bar on its 0-100 continuum, with rubric band boundaries behind and the "
        "modal band labelled."
    )
    return _svg(_W, height, "".join(body), title=title, desc=desc)


# --------------------------------------------------------------------------- figure 2: the trials
def _trial_rows(data: SiteData) -> list[tuple[str, float, float, str]]:
    """The pre-registered MAE gates in run order: (label, model MAE, baseline MAE, verdict). Every
    value is sourced from the evidence table / leaderboard; a gate whose numbers cannot be parsed is
    dropped, never invented."""

    def num(s: str) -> float | None:
        m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
        return float(m.group(0)) if m else None

    failed = (data.gate_verdict or "").lower() or "failed"
    lb = {h: i for i, h in enumerate(data.leaderboard_header)}
    t_i, c_i = lb.get("TEST MAE"), lb.get("comp. MAE")

    def lb_pair(row: list[str]) -> tuple[float | None, float | None]:
        if t_i is None or c_i is None or max(t_i, c_i) >= len(row):
            return None, None
        return num(row[t_i]), num(row[c_i])

    candidates: list[tuple[str, float | None, float | None, str]] = [
        (
            "fair fight · equal capability",
            num(data.fig("E-DEU-MAE-r1")),
            num(data.fig("E-BASE-WMEAN-r1")),
            failed,
        ),
        (
            "fair fight · real capability",
            num(data.fig("E-METHOD-challenge_rp")),
            num(data.fig("E-METHOD-baseline_wmean")),
            failed,
        ),
    ]
    for row in data.leaderboard_rows:
        name = row[0] if row else ""
        model_mae, base_mae = lb_pair(row)
        short = (
            "gravity"
            if "gravity" in name.lower()
            else "regime"
            if "regime" in name.lower()
            else name
        )
        candidates.append((f"successor · {short}", model_mae, base_mae, "failed"))
    oracle = data.fig("E-ORACLE-MAE")
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", oracle)
    candidates.append(
        (
            "noise-floor oracle",
            float(nums[0]) if nums else None,
            float(nums[1]) if len(nums) > 1 else None,
            "ceiling",
        )
    )
    return [(lab, m, b, v) for lab, m, b, v in candidates if m is not None and b is not None]


def trials(data: SiteData) -> str:
    """A horizontal bar pair per pre-registered gate — the model's MAE against the baseline's on a
    shared scale, verdict as a monospace label — ordered as the tests ran, so it reads as a
    sequence of attempts."""
    pal = load_palette()
    rows = _trial_rows(data)
    if not rows:
        return ""
    left, right = 168.0, 66.0
    x0, x1 = left, _W - right
    top = max(5.0, math.ceil(max(max(m, b) for _, m, b, _ in rows) / 5.0) * 5.0)

    def sx(v: float) -> float:
        return x0 + (x1 - x0) * v / top

    pad, legend_h, block, axis_h = 10.0, 26.0, 40.0, 26.0
    height = pad + legend_h + block * len(rows) + axis_h

    body: list[str] = []
    ly = pad + 14.0
    body.append(_rect(x0, ly - 6.0, 20.0, 4.0, fill=pal.low_half))
    body.append(_text(x0 + 26.0, ly, "model", "fig-legend"))
    body.append(_rect(x0 + 80.0, ly - 6.0, 20.0, 4.0, fill=pal.high_half))
    body.append(_text(x0 + 106.0, ly, "baseline", "fig-legend"))

    y = pad + legend_h
    for label, model_mae, base_mae, verdict in rows:
        body.append(_text(4.0, y + 14.0, label, "fig-lab"))
        # model bar (top), baseline bar (below)
        body.append(_rect(x0, y + 4.0, sx(model_mae) - x0, 8.0, fill=pal.low_half))
        body.append(_text(sx(model_mae) + 5.0, y + 11.0, f"{model_mae:g}", "fig-num"))
        body.append(_rect(x0, y + 18.0, sx(base_mae) - x0, 8.0, fill=pal.high_half))
        body.append(_text(sx(base_mae) + 5.0, y + 25.0, f"{base_mae:g}", "fig-num"))
        body.append(_text(x1 + right - 4.0, y + 18.0, verdict, "fig-verdict", "end"))
        y += block

    ay = height - axis_h + 6.0
    body.append(_hline(x0, x1, ay, "fig-axis"))
    for frac in (0.0, 0.5, 1.0):
        v = top * frac
        px = sx(v)
        body.append(_vline(px, ay, ay + 4.0, "fig-axis"))
        anchor = "start" if frac == 0.0 else "end" if frac == 1.0 else "middle"
        body.append(_text(px, ay + 16.0, f"{v:g}", "fig-tick", anchor))
    body.append(
        _text(
            (x0 + x1) / 2.0, height - 2.0, "mean absolute error (0-100 scale)", "fig-tick", "middle"
        )
    )

    title = "The trials"
    desc = (
        f"{len(rows)} pre-registered gates in the order they ran; each shows the model's mean "
        "absolute error against the baseline's on a shared scale, with the verdict."
    )
    return _svg(_W, height, "".join(body), title=title, desc=desc)
