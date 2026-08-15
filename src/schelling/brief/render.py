"""Render a graded question's brief to a self-contained HTML page (Session 56, D56).

Assembles the approved ``first-graded-forecast.html`` layout from three sources — the artifact
figures (:mod:`schelling.brief.data`), the committed prose with its tags resolved
(:mod:`schelling.brief.prose`), and the generated continuum chart (:mod:`schelling.brief.chart`).
The table, the barrels column and the footer citation are computed here; no figure is copied from
the reference. A pure function of the committed tree, so it is byte-identical on re-run.
"""

from __future__ import annotations

import re
from pathlib import Path

from schelling.brief.chart import render_chart
from schelling.brief.css import BRIEF_CSS
from schelling.brief.data import BriefData, gather_brief
from schelling.brief.prose import BriefProseError, parse_prose, resolve_prose

DEFAULT_REPO_URL = "https://github.com/hamzagul07/schelling"
DEFAULT_SITE_URL = "https://schelling-ashen.vercel.app"
BRIEFS_SUBDIR = "briefs"


def prose_path(repo_root: Path, slug: str) -> Path:
    """Where a brief's committed prose lives (a build input, like the paper's DRAFT.md)."""
    return repo_root / "docs" / BRIEFS_SUBDIR / f"{slug}.md"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _flat(text: str) -> str:
    """Collapse internal whitespace/newlines to single spaces (prose is reflowed for HTML)."""
    return " ".join(text.split())


def _beat(text: str, *, sig: bool = False) -> str:
    """One ``date | Title`` + body node in the dossier timeline (the resolved node is accented)."""
    head, _, body = text.partition("\n")
    date, _, title = head.partition("|")
    cls = "beat sig" if sig else "beat"
    return (
        f'<div class="{cls}">'
        f'<p class="d">{_esc(date.strip().upper())}</p>'
        f'<p class="t">{_esc(title.strip())}</p>'
        f'<p class="s">{_esc(_flat(body))}</p></div>'
    )


def _masthead() -> str:
    """The brand bar: wordmark, then honest status tags (an OPEN, GRADED record)."""
    return (
        '<div class="masthead"><span class="mk">SCHELLING</span>'
        '<span class="rt"><span class="tag">OPEN RECORD</span>'
        '<span class="tag sig">GRADED</span></span></div>'
        '<div class="rule-full"><hr></div>'
    )


def _record_panel(data: BriefData) -> str:
    """The dossier record panel: the question's identity and headline result, from artifacts."""
    rows = [
        ("Ref", _esc(data.question_id), ""),
        ("Records", str(len(data.records)), ""),
        ("Settlement", f"{data.actual_continuum:g}", "big"),
        ("Adjustment", f"{data.tag_values()['barrels_actual']} b/d", ""),
    ]
    body = "".join(
        f'<div class="row"><dt>{k}</dt><dd class="{c}">{v}</dd></div>'
        if c
        else f'<div class="row"><dt>{k}</dt><dd>{v}</dd></div>'
        for k, v, c in rows
    )
    return f'<div class="record"><div class="rh">Sealed record</div><dl>{body}</dl></div>'


def _sec(eyebrow: str, title: str, note: str, inner: str) -> str:
    return (
        '<section class="sec">'
        f'<p class="sec-ey">{_esc(eyebrow)}</p>'
        f"<h2>{_esc(title)}</h2>"
        f'<p class="note">{_esc(note)}</p>'
        f"{inner}</section>"
    )


def _verify(data: BriefData, resolved: dict[str, str], *, repo_url: str, site_url: str) -> str:
    repo_display = repo_url.split("://", 1)[-1].rstrip("/")
    site_display = site_url.split("://", 1)[-1].rstrip("/")
    source = f"{resolved['source-label']}, {data.resolved_date}"
    return (
        '<div class="verify"><div class="vh"><p class="seal">'
        f"{_esc(resolved['footer-note'])}</p></div>"
        '<div class="vb">'
        f'<span class="k">Ledger &amp; code</span> '
        f'<a href="{_esc(repo_url)}">{_esc(repo_display)}</a>'
        f'&nbsp; · &nbsp;<span class="k">Site</span> '
        f'<a href="{_esc(site_url)}">{_esc(site_display)}</a>'
        f'&nbsp; · &nbsp;<span class="k">Source for the outcome</span> '
        f'<a href="{_esc(data.citation)}">{_esc(source)}</a>'
        "</div></div>"
    )


def _paragraphs(text: str, cls: str) -> str:
    paras = [p for p in re.split(r"\n[ \t]*\n", text) if p.strip()]
    return "".join(f'<p class="{cls}">{_esc(_flat(p))}</p>' for p in paras)


def _caveats(text: str) -> str:
    """A markdown ``- `` list into ``<ul class="caveats">`` items (continuation lines fold in)."""
    items: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                items.append(" ".join(current))
            current = [stripped[2:].strip()]
        elif stripped:
            current.append(stripped)
    if current:
        items.append(" ".join(current))
    body = "".join(f"<li>{_esc(it)}</li>" for it in items)
    return f'<ul class="caveats">{body}</ul>'


def _table(data: BriefData) -> str:
    """The scores table — best first; barrels inverted from the outcome_map; no hand-typed cell."""
    best = data.best_record
    rows = sorted(data.records, key=lambda r: (r.error, not r.researched))
    trs = []
    for r in rows:
        cls = ' class="best"' if r is best else ""
        trs.append(
            f"<tr{cls}><td>{_esc(r.method_label)}</td>"
            f'<td class="vint">{_esc(r.evidence_label)}</td>'
            f'<td class="num">{r.median:.2f}</td>'
            f'<td class="num">{data.barrels_display(r.median)}</td>'
            f'<td class="num">{r.error:.2f}</td></tr>'
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Method</th><th>Evidence</th><th>Forecast</th>"
        "<th>In barrels</th><th>Off by</th>"
        f"</tr></thead><tbody>{''.join(trs)}</tbody></table></div>"
    )


def render_html(
    data: BriefData,
    resolved: dict[str, str],
    *,
    repo_url: str = DEFAULT_REPO_URL,
    site_url: str = DEFAULT_SITE_URL,
) -> str:
    """Assemble the full brief page from artifact figures, resolved prose, and the chart."""
    title = f"Graded forecast brief — {data.question_id}"
    chart_panel = (
        '<figure><div class="panel-hd"><span>Outcome continuum</span>'
        "<span>Generated, not drawn</span></div>"
        + render_chart(data)
        + f"<figcaption>{_esc(resolved['chart-caption'].upper())}</figcaption></figure>"
    )
    body = (
        _masthead() + '<div class="wrap">'
        f'<p class="eyebrow">{_esc(resolved["eyebrow"])}</p>'
        '<div class="hero"><div>'
        f"<h1>{_esc(resolved['headline'])}</h1>"
        f'<p class="stand">{_esc(_flat(resolved["standfirst"]))}</p>'
        "</div>" + _record_panel(data) + "</div>"
        '<div class="beats">'
        + _beat(resolved["beat-sealed"])
        + _beat(resolved["beat-resolved"], sig=True)
        + _beat(resolved["beat-graded"])
        + "</div>"
        + _sec(
            "Outcome continuum",
            resolved["landed-title"],
            _flat(resolved["landed-note"]),
            chart_panel,
        )
        + _sec(
            "Scored by distance",
            resolved["scores-title"],
            _flat(resolved["scores-note"]),
            _table(data),
        )
        + '<section class="sec"><p class="sec-ey">The reading</p>'
        + f"<h2>{_esc(resolved['shows-title'])}</h2>"
        + '<div class="cols"><div>'
        + _paragraphs(resolved["commentary-pull"], "pull")
        + _paragraphs(resolved["commentary-body"], "body")
        + "</div><div>"
        + _paragraphs(resolved["caveats-pull"], "pull")
        + _caveats(resolved["caveats"])
        + "</div></div></section>"
        + _verify(data, resolved, repo_url=repo_url, site_url=site_url)
        + "</div>"
    )
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title>"
        f"<style>{BRIEF_CSS}</style>"
        "</head><body>" + body + "</body></html>"
    )


def render_page(
    question_id: str,
    repo_root: Path,
    *,
    repo_url: str = DEFAULT_REPO_URL,
    site_url: str = DEFAULT_SITE_URL,
) -> tuple[str, str]:
    """Render ``question_id``'s brief to ``(slug, html)`` — pure, writes nothing.

    Raises :class:`~schelling.brief.data.BriefNotGradedError` on an ungraded question, or
    :class:`~schelling.brief.prose.BriefProseError` on absent/malformed prose or an unresolved tag.
    """
    data = gather_brief(question_id, repo_root)
    path = prose_path(repo_root, data.slug)
    if not path.exists():
        raise BriefProseError(
            f"no committed prose for {question_id} at {path} — write the brief's "
            f"docs/{BRIEFS_SUBDIR}/{data.slug}.md before building."
        )
    resolved = resolve_prose(parse_prose(path.read_text()), data.tag_values())
    return data.slug, render_html(data, resolved, repo_url=repo_url, site_url=site_url)


def build_brief(
    question_id: str,
    repo_root: Path,
    *,
    docs_dir: Path | None = None,
    repo_url: str = DEFAULT_REPO_URL,
    site_url: str = DEFAULT_SITE_URL,
) -> Path:
    """Render and WRITE the brief under ``docs_dir/briefs/<slug>.html``; return the written path."""
    slug, html = render_page(question_id, repo_root, repo_url=repo_url, site_url=site_url)
    out_dir = (docs_dir if docs_dir is not None else repo_root / "docs") / BRIEFS_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slug}.html"
    out.write_text(html)
    return out
