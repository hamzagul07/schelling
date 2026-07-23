"""Render the static site from :class:`SiteData` and diff it against the committed pages (D31, D33).

Every page is plain, self-contained HTML linking one relative stylesheet (``site.css``); the only
external references are navigational ``<a href>`` links to the public repo (rubrics, the draft, the
source) — never embedded resources, so each page renders fully offline. No figure is written by
hand: the page builders interpolate only fields of :class:`SiteData`, which are parsed from
artifacts. The markup structure and classes follow Hassan's approved ``site-reference-index.html``
(D33): a nav, a two-line serif ``h1`` whose second line carries the accent, stat cards, and a
div-based ledger where every full SHA-256 sits on its own monospace line beneath the row.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from schelling.site.css import SITE_CSS
from schelling.site.data import SiteData, gather
from schelling.site.figures import forecast_landscape, trials

DEFAULT_REPO_URL = "https://github.com/hamzagul07/schelling"

# nav order (the brand links home; Source is external) — labels double as the aria-current key.
_NAVLINKS = [
    ("ledger.html", "Ledger"),
    ("findings.html", "Findings"),
    ("paper.html", "Paper"),
    ("reports/", "Reports"),
]
_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _first_num(text: str) -> str:
    m = _NUM.search(text)
    return m.group(0) if m else ""


def _two_nums(text: str) -> str:
    """The first two numbers in a compound evidence value, joined ``a / b`` (e.g. ``23.84 vs
    22.99`` -> ``23.84 / 22.99``). Empty if fewer than two are present."""
    nums = _NUM.findall(text)
    return " / ".join(nums[:2]) if len(nums) >= 2 else ""


def _delta_num(cells: list[str]) -> str:
    """The signed delta from a leaderboard row — the first cell that begins with + or - (its number
    only, e.g. ``+0.83 [-0.15, +1.91]`` -> ``+0.83``). Empty when the row carries no delta cell."""
    for cell in cells:
        c = cell.strip()
        if c[:1] in "+-":
            return _first_num(c)
    return ""


def _blob(repo_url: str, path: str, text: str) -> str:
    """A navigational link to a repository file (rubrics, DRAFT.md — they live above ``docs/`` and
    are not served by the host, so they are linked at the public repo, not relatively)."""
    return f'<a href="{_esc(repo_url)}/blob/main/{_esc(path)}">{_esc(text)}</a>'


def _nav(current: str, prefix: str, repo_url: str) -> str:
    brand = f'<a class="brand" href="{prefix}index.html">schelling</a>'
    links = []
    for href, label in _NAVLINKS:
        cur = ' aria-current="page"' if label == current else ""
        links.append(f'<a href="{prefix}{href}"{cur}>{_esc(label)}</a>')
    links.append(f'<a href="{_esc(repo_url)}">Source</a>')
    return (
        '<nav><div class="wrap">'
        + brand
        + '<span class="navlinks">'
        + "".join(links)
        + "</span></div></nav>"
    )


def _shell(
    *, title: str, description: str, current: str, body: str, repo_url: str, prefix: str
) -> str:
    host = repo_url.split("://", 1)[-1]
    footer = (
        "<footer>Every figure on this site regenerates from repository artifacts — no number is "
        f'hand-typed. · <a href="{_esc(repo_url)}">{_esc(host)}</a></footer>'
    )
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="description" content="{_esc(description)}">'
        f"<title>{_esc(title)}</title>"
        f'<link rel="stylesheet" href="{prefix}site.css">'
        "</head><body>"
        + _nav(current, prefix, repo_url)
        + f'<div class="wrap">{body}{footer}</div>'
        + "</body></html>"
    )


def _hero(eyebrow: str, line1: str, turn: str, lede: str, actions: str) -> str:
    return (
        f'<p class="eyebrow">{_esc(eyebrow)}</p>'
        f'<h1>{_esc(line1)}<span class="turn">{_esc(turn)}</span></h1>'
        f'<p class="lede">{_esc(lede)}</p>'
        + (f'<div class="actions">{actions}</div>' if actions else "")
    )


def _stat(k: str, v: str, *, date: bool = False) -> str:
    cls = "v date" if date else "v"
    return f'<div class="stat"><p class="k">{_esc(k)}</p><p class="{cls}">{_esc(v)}</p></div>'


def _stats(data: SiteData, *, tests: bool) -> str:
    cards = (
        _stat("Forecasts sealed", str(data.sealed_count))
        + _stat("Graded", str(data.graded_count))
        + _stat("First grading", data.grading_date, date=True)
        + (_stat("Tests", data.test_count) if tests else "")
    )
    return f'<div class="stats">{cards}</div>'


def _numbered(sections: list[str]) -> str:
    """Wrap each section body in a numbered ``<section>``: a hairline rule above (the section's
    border-top) with its section number in monospace at the left (D34.4). The number itself is a
    CSS counter (``.snum::before``), so no ordinal is hand-typed into the HTML."""
    return "".join(f'<section><p class="snum"></p>{inner}</section>' for inner in sections)


def _figure(svg: str, caption: str) -> str:
    """A figure with its monospace caption. Empty string when the figure could not be generated."""
    if not svg:
        return ""
    return (
        f'<figure class="figure">{svg}'
        f'<figcaption class="fig-cap">{_esc(caption)}</figcaption></figure>'
    )


def _honesty_note(data: SiteData) -> str:
    """The ledger note — the graded count sits beside the sealed count in the stat cards above; this
    states plainly that nothing is graded, so no accuracy is claimed (D31.5)."""
    if data.graded_count == 0:
        tail = "Nothing here has been graded yet, so no accuracy is claimed."
    else:
        tail = f"{data.graded_count} of {data.sealed_count} sealed forecasts are now graded."
    return (
        '<p class="note">Each row is the SHA-256 of a complete forecast record, committed to this '
        "public repository before its event resolved and anchored in the bitcoin blockchain by "
        f"OpenTimestamps. {tail}</p>"
    )


def _ledger(data: SiteData) -> str:
    """The div-based ledger: a metadata line per row, with the full SHA-256 on its own monospace
    line beneath (D33) — never inside a table cell. Shows every sealed row."""
    head = (
        '<div class="lhead"><span class="q">Question</span><span class="m">Model</span>'
        '<span class="v">Median</span><span class="d">Resolves</span></div>'
    )
    rows = []
    for r in data.ledger:
        graded = r.question in data.graded_questions
        chip = "graded" if graded else "sealed"
        resolves = data.questions.get(r.question)
        date = resolves.resolution_date if resolves else ""
        rows.append(
            '<div class="lrow"><div class="lmain">'
            f'<span class="q"><code>{_esc(r.question)}</code> '
            f'<span class="chip">{chip}</span></span>'
            f'<span class="m">{_esc(r.model)}</span>'
            f'<span class="v">{_esc(r.median)}</span>'
            f'<span class="d">{_esc(date)}</span></div>'
            f'<p class="hash">{_esc(r.sha256)}</p></div>'
        )
    return '<div class="ledger">' + head + "".join(rows) + "</div>"


def _gate_rows(data: SiteData) -> str:
    """The pre-registered gates and their numbers — every figure pulled from the evidence table and
    the leaderboard. A gate whose numbers cannot be sourced is dropped, never invented (D33.2)."""
    failed = (data.gate_verdict or "").lower() or "failed"
    deltas = [_delta_num(cells) for cells in data.leaderboard_rows]
    successor = " / ".join(d for d in deltas if d)
    gates = [
        ("Replication of the published reference case", data.fig("E-REPL-MEDIAN"), "passed"),
        (
            "Challenge model vs the weighted mean",
            _join(data.fig("E-DEU-MAE-r1"), data.fig("E-BASE-WMEAN-r1")),
            failed,
        ),
        (
            "The same fight with real capabilities",
            _join(
                _first_num(data.fig("E-METHOD-challenge_rp")),
                _first_num(data.fig("E-METHOD-baseline_wmean")),
            ),
            failed,
        ),
        ("Two successor models, held-out test split", successor, failed),
        ("Flexible oracle — is there signal left?", _two_nums(data.fig("E-ORACLE-MAE")), "ceiling"),
    ]
    out = []
    for label, numbers, verdict in gates:
        if not numbers:
            continue  # no artifact source for this figure — drop the element
        out.append(
            f'<div class="gate"><span class="g">{_esc(label)}</span>'
            f'<span class="n">{_esc(numbers)}</span>'
            f'<span class="r">{_esc(verdict)}</span></div>'
        )
    return '<div class="gates">' + "".join(out) + "</div>"


def _join(a: str, b: str) -> str:
    return f"{a} / {b}" if a and b else ""


# --------------------------------------------------------------------------- index
def _index_body(data: SiteData, repo_url: str) -> str:
    actions = (
        '<a class="btn primary" href="paper.html">Read the paper</a>'
        '<a class="btn" href="ledger.html">The sealed ledger</a>'
        f'<a class="btn" href="{_esc(repo_url)}">Source</a>'
    )
    hero = _hero(
        "open forecasting engine · agpl · research preview",
        "The CIA's forecasting model was never checkable.",
        "Now it is.",
        "An open replication of the Bueno de Mesquita group decision model, with a measured "
        "predictability ceiling, a pre-registered successor search, and every forecast sealed by "
        "cryptographic hash before the event resolves.",
        actions,
    )
    landscape = (
        "<h2>The forecast landscape</h2>"
        '<p class="sub">Every sealed forecast on its own continuum — median and 80% interval, with '
        "the rubric bands behind.</p>"
        + _figure(
            forecast_landscape(data),
            "Fig. 1 — the forecast landscape, generated from the "
            "sealed ledger and its interval snapshot.",
        )
    )
    verify = (
        "<pre>schelling verify runs/&lt;record&gt;.json\n"
        "ots verify ledger-proofs/FORECASTS.md-&lt;hash&gt;.ots -f FORECASTS.md</pre>"
    )
    ledger = (
        "<h2>The sealed ledger</h2>"
        '<p class="sub">Committed before resolution. Anchored in bitcoin. Verifiable by anyone.</p>'
        + _ledger(data)
        + _honesty_note(data)
        + verify
    )
    gates = (
        "<h2>What the tests found</h2>"
        '<p class="sub">Every gate fixed in writing before the result existed. None was moved.</p>'
        + _gate_rows(data)
        + '<p class="note">The celebrated model loses to the average of its own inputs, and an '
        "overfit-capable probe finds nothing beyond that average to extract. What made the lineage "
        "work was never the equations — it was the discipline of turning expert judgement into "
        "structured numbers. Structure, not magic.</p>"
    )
    return hero + _stats(data, tests=True) + _numbered([landscape, ledger, gates])


# --------------------------------------------------------------------------- ledger
def _ledger_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "the sealed ledger",
        "The forecasts are sealed",
        "before they resolve.",
        "Commit-reveal: each forecast is sealed by the SHA-256 of its run record before the event "
        "resolves. The record files are gitignored, so no number can be quietly edited after the "
        "outcome is known.",
        "",
    )
    landscape = (
        "<h2>The forecast landscape</h2>"
        '<p class="sub">Every sealed forecast on its own continuum — median and 80% interval, with '
        "the rubric bands behind and the modal band labelled.</p>"
        + _figure(
            forecast_landscape(data),
            "Fig. 1 — the forecast landscape, generated from the "
            "sealed ledger and its interval snapshot.",
        )
    )
    ledger = (
        "<h2>Every sealed forecast</h2>"
        '<p class="sub">All rows, committed to this public repository ahead of resolution.</p>'
        + _ledger(data)
        + _honesty_note(data)
    )
    q_items = []
    for info in data.questions.values():
        graded = info.question_id in data.graded_questions
        chip = "graded" if graded else "sealed"
        q_items.append(
            f'<li class="ritem">{_blob(repo_url, info.rubric_file, info.question_id)}'
            f'<p class="rf">resolves {_esc(info.resolution_date)} · {chip} · '
            "pre-registered grading rubric</p></li>"
        )
    questions = (
        "<h2>Questions and rubrics</h2>"
        '<p class="sub">Each question&rsquo;s resolution criterion was fixed in writing before '
        "resolution.</p>"
        f'<ul class="rlist">{"".join(q_items)}</ul>'
    )
    verify = (
        "<h2>How to verify</h2>"
        '<p class="sub">Anyone can audit a sealed forecast without trusting us.</p>'
        "<h3>Recompute and match</h3>"
        "<pre>schelling verify runs/&lt;record&gt;.json</pre>"
        '<p class="note">Recomputes the record file&rsquo;s SHA-256 and matches it to the row '
        "above, recomputes the canonical inputs hash, and re-solves the embedded game with the "
        "record&rsquo;s own seed to confirm the forecast reproduces byte-for-byte.</p>"
        "<h3>External time anchor</h3>"
        "<pre>ots verify ledger-proofs/FORECASTS.md-&lt;hash&gt;.ots -f FORECASTS.md</pre>"
        '<p class="note">Each seal timestamps the ledger in the bitcoin blockchain, which cannot '
        f"be backdated. The full ledger document is "
        f"{_blob(repo_url, 'FORECASTS.md', 'FORECASTS.md')}.</p>"
    )
    return hero + _stats(data, tests=False) + _numbered([landscape, ledger, questions, verify])


# --------------------------------------------------------------------------- findings
def _findings_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "the method, and its negative results",
        "We gave the model",
        "every advantage.",
        "A fair, pre-registered evaluation of the reconstructed model — reported with the same "
        "prominence whether it passes or fails. It fails, and that is the finding.",
        "",
    )
    trials_sec = (
        "<h2>The trials</h2>"
        '<p class="sub">Each pre-registered gate, in the order it ran: the model&rsquo;s error '
        "against the baseline&rsquo;s, on one scale.</p>"
        + _figure(
            trials(data),
            "Fig. 2 — the trials, generated from the backtest and evidence table; lower is better.",
        )
    )
    gates = (
        "<h2>What the tests found</h2>"
        '<p class="sub">Every gate fixed in writing before the result existed. None was moved.</p>'
        + _gate_rows(data)
    )
    oracle = data.fig("E-ORACLE-MAE")
    gap = data.fig("E-ORACLE-GAP")
    ceiling = ""
    if oracle and gap:
        ceiling = (
            "<h2>The ceiling</h2>"
            f'<p class="body">A deliberately flexible, cross-validated oracle scores '
            f"{_esc(oracle)} against the compromise mean — a gap of {_esc(gap)}. Even an "
            "optimistic flexible model does not beat the mean: there is essentially no signal "
            "beyond the "
            "influence-weighted average, which is why every model tried fails to beat it.</p>"
        )
    # successor leaderboard, rendered as gate-style rows (no table — hashes never live in a table,
    # and the same rhythm carries across pages)
    lb_rows = []
    for cells in data.leaderboard_rows:
        name = cells[0] if cells else ""
        delta = _delta_num(cells)
        if not name or not delta:
            continue
        lb_rows.append(
            f'<div class="gate"><span class="g">{_esc(name)}</span>'
            f'<span class="n">Δ {_esc(delta)}</span>'
            '<span class="r">no</span></div>'
        )
    successor = ""
    if lb_rows:
        successor = (
            "<h2>Successor search</h2>"
            '<p class="sub">A pre-registered train/dev/test split, committed before any fitting; '
            "each candidate scored once on the untouched test split.</p>"
            '<div class="gates">'
            + "".join(lb_rows)
            + "</div>"
            + (
                f'<p class="note">{_esc(data.successor_verdict)}</p>'
                if data.successor_verdict
                else ""
            )
            + f'<p class="note">The full backtest is '
            f"{_blob(repo_url, 'BACKTEST.md', 'BACKTEST.md')}.</p>"
        )
    sections = [gates, trials_sec]
    if ceiling:
        sections.append(ceiling)
    if successor:
        sections.append(successor)
    return hero + _numbered(sections)


# --------------------------------------------------------------------------- paper
def _paper_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "the paper",
        "Structure,",
        "not magic.",
        "An open replication and predictability ceiling for the Bueno de Mesquita forecasting "
        "model. Every cited number regenerates from repository artifacts by a single command.",
        f'<a class="btn primary" href="{_esc(repo_url)}/blob/main/paper/DRAFT.md">'
        "Read the draft</a>"
        f'<a class="btn" href="{_esc(repo_url)}">Source</a>',
    )
    sections = []
    if data.abstract:
        sections.append(f'<h2>Abstract</h2><p class="body">{_esc(data.abstract)}</p>')
    sections.append(
        "<h2>Read the draft</h2>"
        f'<p class="body">The full working draft — assembled deterministically from the section '
        "files and the evidence table, every cited number carrying a per-claim provenance footnote "
        f"— is {_blob(repo_url, 'paper/DRAFT.md', 'paper/DRAFT.md')}. Regenerate the evidence base "
        "with <code>schelling paper-evidence</code>.</p>"
    )
    if data.bibliography:
        items = "".join(f"<li>{_esc(entry)}</li>" for entry in data.bibliography)
        sections.append(f'<h2>Bibliography</h2><ul class="bib">{items}</ul>')
    return hero + _numbered(sections)


# --------------------------------------------------------------------------- reports
def _reports_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "rendered dossiers and reports",
        "The full record,",
        "per question.",
        "Two-audience reports and research dossiers rendered from sealed run records. Each is "
        "self-contained HTML with inline figures — open one directly.",
        "",
    )
    if data.reports:
        items = "".join(
            f'<li class="ritem"><a href="{_esc(r.filename)}">{_esc(r.title)}</a>'
            f'<p class="rf">{_esc(r.filename)}</p></li>'
            for r in data.reports
        )
        listing = f'<h2>Published reports</h2><ul class="rlist">{items}</ul>'
    else:
        listing = (
            '<h2>Published reports</h2><p class="note">No rendered reports are published yet. '
            "Reports are generated with <code>schelling report</code> / "
            "<code>schelling dossier</code> and copied into docs/reports/.</p>"
        )
    return hero + _numbered([listing])


def build_site(
    repo_root: Path, *, repo_url: str = DEFAULT_REPO_URL, data: SiteData | None = None
) -> dict[str, str]:
    """Return every site file as ``{relative-posix-path: content}`` (a pure function of the repo).

    Keys: the five HTML pages, the shared ``site.css``, and ``.nojekyll`` (so GitHub Pages serves
    the files verbatim without a Jekyll pass)."""
    d = data if data is not None else gather(repo_root)
    pages = {
        "index.html": (
            _index_body(d, repo_url),
            "Schelling — an open forecasting engine",
            "The thesis",
            "",
            "An open, continuously-audited replication of the Bueno de Mesquita forecasting model.",
        ),
        "ledger.html": (
            _ledger_body(d, repo_url),
            "Ledger — Schelling",
            "Ledger",
            "",
            "The sealed commit-reveal forecast ledger, with verification instructions.",
        ),
        "findings.html": (
            _findings_body(d, repo_url),
            "Findings — Schelling",
            "Findings",
            "",
            "The pre-registered evaluation, the ceiling result, and the successor search.",
        ),
        "paper.html": (
            _paper_body(d, repo_url),
            "Paper — Schelling",
            "Paper",
            "",
            "Abstract, draft, and bibliography of the open replication paper.",
        ),
        "reports/index.html": (
            _reports_body(d, repo_url),
            "Reports — Schelling",
            "Reports",
            "../",
            "Index of rendered dossiers and reports.",
        ),
    }
    out: dict[str, str] = {"site.css": SITE_CSS + "\n", ".nojekyll": ""}
    for path, (body, title, current, prefix, desc) in pages.items():
        out[path] = _shell(
            title=title,
            description=desc,
            current=current,
            body=body,
            repo_url=repo_url,
            prefix=prefix,
        )
    return out


def write_site(repo_root: Path, docs_dir: Path, *, repo_url: str = DEFAULT_REPO_URL) -> list[str]:
    """Write every site file under ``docs_dir``; return the sorted relative paths written."""
    files = build_site(repo_root, repo_url=repo_url)
    for rel, content in files.items():
        dest = docs_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return sorted(files)


def check_site(repo_root: Path, docs_dir: Path, *, repo_url: str = DEFAULT_REPO_URL) -> list[str]:
    """Return the sorted relative paths whose committed content differs from a fresh regeneration
    (empty when the site is in sync). Missing files count as drift (D31.2)."""
    files = build_site(repo_root, repo_url=repo_url)
    drift: list[str] = []
    for rel, content in files.items():
        dest = docs_dir / rel
        if not dest.exists() or dest.read_text() != content:
            drift.append(rel)
    return sorted(drift)
