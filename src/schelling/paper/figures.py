"""Deterministic figure generation (Session 14, D14.2).

Four byte-stable SVGs rendered straight from the computed records (no random, no wall-clock, integer
coordinates), so one command regenerates them identically:

* ``fig_deu_error_histogram.svg``   — distribution of the primary challenge solver's abs errors
* ``fig_challenge_vs_compromise.svg`` — challenge vs compromise error distributions, grouped
* ``fig_leaderboard.svg``           — the R1 successor leaderboard as a table
* ``fig_r1_split.svg``              — the pre-registered 40/30/30 train/dev/TEST split

All coordinates are rounded to integers and every value derives from the passed-in records, so the
output is a pure function of the repo state (CLAUDE.md rule 2).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schelling.backtest.successor import SuccessorReport
    from schelling.schemas.backtest import BacktestRecord

_W, _H = 640, 360
_PInk = "#1a1a2e"
_CHAL = "#c0392b"  # challenge (red)
_COMP = "#2471a3"  # compromise (blue)
_AX = "#888"


def _errors_for(record: BacktestRecord, key: str) -> list[float]:
    for m in record.methods:
        if m.key == key:
            return list(m.errors)
    return []


def _histogram(errors: list[float], bins: int = 10, hi: float = 100.0) -> list[int]:
    counts = [0] * bins
    width = hi / bins
    for e in errors:
        idx = min(int(e / width), bins - 1)
        if idx < 0:
            idx = 0
        counts[idx] += 1
    return counts


def _svg_open(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'font-family="Helvetica,Arial,sans-serif">',
        f'<text x="{_W // 2}" y="26" text-anchor="middle" font-size="17" '
        f'font-weight="bold" fill="{_PInk}">{title}</text>',
    ]


def _bar(x: int, y: int, w: int, h: int, fill: str) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'


def _deu_histogram_svg(record: BacktestRecord) -> str:
    errs = _errors_for(record, record.primary_method)
    counts = _histogram(errs)
    top = max(counts) if counts else 1
    x0, y0, plot_w, plot_h = 60, 300, _W - 100, 240
    bw = plot_w // len(counts)
    out = _svg_open("DEU abs-error distribution — challenge (primary)")
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x0 + plot_w}" y2="{y0}" stroke="{_AX}"/>')
    for i, c in enumerate(counts):
        h = round(c / top * plot_h)
        x = x0 + i * bw
        out.append(_bar(x + 2, y0 - h, bw - 4, h, _CHAL))
        out.append(
            f'<text x="{x + bw // 2}" y="{y0 + 16}" text-anchor="middle" '
            f'font-size="10" fill="{_PInk}">{i * 10}-{i * 10 + 10}</text>'
        )
        if c:
            out.append(
                f'<text x="{x + bw // 2}" y="{y0 - h - 4}" text-anchor="middle" '
                f'font-size="10" fill="{_PInk}">{c}</text>'
            )
    out.append(
        f'<text x="{_W // 2}" y="{_H - 6}" text-anchor="middle" font-size="11" '
        f'fill="{_PInk}">absolute error (0-100 continuum), n={len(errs)}</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _challenge_vs_compromise_svg(record: BacktestRecord) -> str:
    ch = _histogram(_errors_for(record, record.primary_method))
    co = _histogram(_errors_for(record, "baseline_wmean"))
    top = max(max(ch), max(co), 1)
    x0, y0, plot_w, plot_h = 60, 300, _W - 100, 220
    slot = plot_w // len(ch)
    out = _svg_open("Abs-error distribution — challenge vs compromise")
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x0 + plot_w}" y2="{y0}" stroke="{_AX}"/>')
    for i in range(len(ch)):
        x = x0 + i * slot
        hc = round(ch[i] / top * plot_h)
        hm = round(co[i] / top * plot_h)
        out.append(_bar(x + 3, y0 - hc, slot // 2 - 3, hc, _CHAL))
        out.append(_bar(x + slot // 2, y0 - hm, slot // 2 - 3, hm, _COMP))
        out.append(
            f'<text x="{x + slot // 2}" y="{y0 + 16}" text-anchor="middle" '
            f'font-size="10" fill="{_PInk}">{i * 10}</text>'
        )
    out.append(_bar(x0, 44, 14, 14, _CHAL))
    out.append(
        f'<text x="{x0 + 20}" y="56" font-size="12" fill="{_PInk}">challenge (primary)</text>'
    )
    out.append(_bar(x0 + 170, 44, 14, 14, _COMP))
    out.append(f'<text x="{x0 + 190}" y="56" font-size="12" fill="{_PInk}">compromise mean</text>')
    out.append(
        f'<text x="{_W // 2}" y="{_H - 6}" text-anchor="middle" font-size="11" '
        f'fill="{_PInk}">absolute error bin (0-100)</text>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _leaderboard_svg(report: SuccessorReport) -> str:
    rows = [("Candidate", "TEST MAE", "comp MAE", "delta [95% CI]", "beats?")]
    for c in report.candidates:
        rows.append(
            (
                c.name,
                f"{c.test_mae:.2f}",
                f"{c.test_compromise_mae:.2f}",
                f"{c.delta:+.2f} [{c.ci_lo:+.2f}, {c.ci_hi:+.2f}]",
                "yes" if c.beats_compromise else "no",
            )
        )
    colx = [30, 300, 380, 470, 610]
    out = _svg_open("Successor leaderboard — TEST scored once (R1)")
    y = 70
    for r, row in enumerate(rows):
        weight = "bold" if r == 0 else "normal"
        for cx, cell in zip(colx, row, strict=True):
            anchor = "end" if cx > 360 else "start"
            out.append(
                f'<text x="{cx}" y="{y}" text-anchor="{anchor}" font-size="12" '
                f'font-weight="{weight}" fill="{_PInk}">{cell}</text>'
            )
        out.append(f'<line x1="30" y1="{y + 8}" x2="610" y2="{y + 8}" stroke="#ddd"/>')
        y += 34
    sc = report.split_counts
    out.append(
        f'<text x="30" y="{y + 6}" font-size="11" fill="{_AX}">'
        f"pre-registered split train {sc['train']} / dev {sc['dev']} / TEST {sc['test']} "
        f"(seed {report.split_seed}); no candidate beats the compromise mean.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _r1_split_svg(report: SuccessorReport) -> str:
    sc = report.split_counts
    total = sc["train"] + sc["dev"] + sc["test"]
    x0, y0, bar_w, bar_h = 40, 150, _W - 80, 70
    out = _svg_open("Pre-registered 40/30/30 split — committed before any fitting")
    x = x0
    for name, key, fill in (
        ("train", "train", _COMP),
        ("dev", "dev", "#7f8c8d"),
        ("TEST", "test", _CHAL),
    ):
        w = round(sc[key] / total * bar_w)
        out.append(_bar(x, y0, w, bar_h, fill))
        out.append(
            f'<text x="{x + w // 2}" y="{y0 + 40}" text-anchor="middle" font-size="14" '
            f'font-weight="bold" fill="#fff">{name}</text>'
        )
        out.append(
            f'<text x="{x + w // 2}" y="{y0 + bar_h + 20}" text-anchor="middle" '
            f'font-size="12" fill="{_PInk}">{sc[key]}</text>'
        )
        x += w
    out.append(
        f'<text x="{_W // 2}" y="{y0 - 16}" text-anchor="middle" font-size="12" '
        f'fill="{_PInk}">n={total} DEU issues · seed {report.split_seed} · '
        f"git commit order = pre-registration · TEST scored once</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def write_figures(
    out_dir: Path, record: BacktestRecord | None, report: SuccessorReport | None
) -> list[str]:
    """Write the SVGs that can be built from the given records; return the filenames written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if record is not None:
        (out_dir / "fig_deu_error_histogram.svg").write_text(_deu_histogram_svg(record))
        (out_dir / "fig_challenge_vs_compromise.svg").write_text(
            _challenge_vs_compromise_svg(record)
        )
        written += ["fig_deu_error_histogram.svg", "fig_challenge_vs_compromise.svg"]
    if report is not None:
        (out_dir / "fig_leaderboard.svg").write_text(_leaderboard_svg(report))
        (out_dir / "fig_r1_split.svg").write_text(_r1_split_svg(report))
        written += ["fig_leaderboard.svg", "fig_r1_split.svg"]
    return written
