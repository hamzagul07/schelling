"""Render the Sobol panel **beside** the tornado, each explicitly labelled (Session 40, D40.3).

Kept out of the default forecast report so sealed reports stay byte-identical; the ``schelling
sobol`` command assembles this standalone two-panel page on demand. Pure and deterministic.
"""

from __future__ import annotations

from schelling.mc.sobol import SobolResult
from schelling.report import svg
from schelling.report.render import _esc, _page
from schelling.schemas.forecast import SensitivityEntry


def _tornado_figure(entries: list[SensitivityEntry], baseline: float) -> str:
    rows = [
        svg.TornadoRow(e.parameter, e.forecast_at_low, e.forecast_at_high, e.swing) for e in entries
    ]
    return svg.tornado(rows, baseline=baseline)


def sobol_panel_html(
    question_id: str,
    entries: list[SensitivityEntry],
    baseline: float,
    sobol: SobolResult,
) -> str:
    """A page with the tornado and the Sobol indices side by side, each labelled by what it means.

    The two panels answer different questions and are never merged: the tornado shows a single
    parameter's swing between its low and high; Sobol shows each parameter's share of the total
    output variance, including the variance it drives through interactions with others.
    """
    order = sorted(range(sobol.k), key=lambda i: -sobol.total_order[i])
    first_rows = [svg.BarRow(sobol.labels[i], sobol.first_order[i]) for i in order]
    total_rows = [svg.BarRow(sobol.labels[i], sobol.total_order[i]) for i in order]
    parts = [
        f"<h1>{_esc(question_id)} — sensitivity panels</h1>",
        "<h2>Tornado — single-parameter swings</h2>",
        "<p class='sub'>Each bar is the forecast swing as one parameter moves from its low to its "
        "high, all others held at mode. One-at-a-time; no interactions.</p>",
        f"<figure>{_tornado_figure(entries, baseline)}</figure>",
        "<h2>Sobol — share of output variance (including interactions)</h2>",
        f"<p class='sub'>{sobol.model} solver, N={sobol.n}, cost {sobol.cost} solves, "
        f"seed {sobol.seed}. First-order = the parameter alone; total-order = the parameter "
        "including every interaction it takes part in (total &#8805; first).</p>",
    ]
    if sobol.k == 0:
        parts.append("<p>No ranged parameters — every input is a point estimate (no variance).</p>")
    else:
        parts += [
            "<h3>First-order S<sub>i</sub></h3>",
            f"<figure>{svg.hbars(first_rows)}</figure>",
            "<h3>Total-order S<sub>Ti</sub></h3>",
            f"<figure>{svg.hbars(total_rows)}</figure>",
        ]
    return _page(f"{question_id} — sensitivity", "".join(parts))
