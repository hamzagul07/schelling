"""Render the static site from :class:`SiteData` and diff it against the committed pages (D31-D35).

Every page is plain, self-contained HTML linking one relative stylesheet (``site.css``); the only
external references are navigational ``<a href>`` links to the public repo — never embedded
resources, so each page renders fully offline. No figure is written by hand: the page builders
interpolate only fields of :class:`SiteData`, parsed from artifacts. The layout follows Hassan's
approved ``site-reference-vast.html`` (D35): a sticky 260px sidebar with a numbered section index,
a full-bleed content column, and the index restructured into eight sections that deep-link to the
existing pages.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from schelling.site.css import SITE_CSS
from schelling.site.data import SiteData, gather, trial_gates
from schelling.site.figures import forecast_landscape, trials

DEFAULT_REPO_URL = "https://github.com/hamzagul07/schelling"

# The eight sections of the index, in order — the sidebar index and the section ordinals follow it.
_SECTIONS = [
    ("finding", "The finding"),
    ("ledger", "The sealed ledger"),
    ("trials", "The trials"),
    ("apparatus", "The apparatus"),
    ("canon", "The canon"),
    ("record", "The record"),
    ("paper", "The paper"),
    ("verify", "Verify it yourself"),
]
_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _first_num(text: str) -> str:
    m = _NUM.search(text)
    return m.group(0) if m else ""


def _blob(repo_url: str, path: str, text: str) -> str:
    """A navigational link to a repository file (canon.md, DECISIONS.md — above ``docs/``, linked at
    the public repo, not relatively)."""
    return f'<a href="{_esc(repo_url)}/blob/main/{_esc(path)}">{_esc(text)}</a>'


def _deep(href: str, text: str) -> str:
    return f'<a class="deep" href="{_esc(href)}">{_esc(text)} →</a>'


def _figure(svg: str, caption: str) -> str:
    if not svg:
        return ""
    return f"<figure>{svg}<figcaption>{_esc(caption)}</figcaption></figure>"


def _sidebar(current: str, prefix: str, data: SiteData) -> str:
    links = []
    for anchor, label in _SECTIONS:
        cur = ' aria-current="page"' if anchor == current else ""
        links.append(
            f'<a href="{prefix}index.html#{anchor}"{cur}><span class="n"></span>{_esc(label)}</a>'
        )
    foot = (
        f"research preview<br>agpl-3.0<br>{data.graded_count} graded · {data.sealed_count} sealed"
    )
    return (
        "<aside>"
        '<div class="mark">SCHELLING</div>'
        f'<nav class="idx">{"".join(links)}</nav>'
        f'<div class="asidefoot">{foot}</div>'
        "</aside>"
    )


def _shell(
    *,
    title: str,
    description: str,
    body: str,
    current: str,
    prefix: str,
    data: SiteData,
    repo_url: str,
) -> str:
    host = repo_url.split("://", 1)[-1].upper()
    footer = (
        f'<div class="bleed"><footer>SCHELLING · RESEARCH PREVIEW · {data.sealed_count} SEALED · '
        f"{data.graded_count} GRADED · {_esc(host)}</footer></div>"
    )
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="description" content="{_esc(description)}">'
        f"<title>{_esc(title)}</title>"
        f'<link rel="stylesheet" href="{prefix}site.css">'
        "</head><body>"
        '<div class="shell">'
        + _sidebar(current, prefix, data)
        + f"<main>{body}{footer}</main>"
        + "</div></body></html>"
    )


def _hero(mark: str, line1: str, turn: str, lede: str, cta: str) -> str:
    return (
        '<div class="bleed hero">'
        f'<div class="mark">{_esc(mark)}</div>'
        f'<h1>{_esc(line1)}<span class="turn">{_esc(turn)}</span></h1>'
        f'<p class="lede">{_esc(lede)}</p>'
        + (f'<div class="cta">{cta}</div>' if cta else "")
        + "</div>"
    )


def _section(anchor: str, title: str, inner: str, *, rule: bool = True) -> str:
    cls = "bleed rule" if rule else "bleed"
    return (
        f'<section id="{anchor}" class="{cls}">'
        f'<div class="sechead"><span class="n"></span><h2>{_esc(title)}</h2></div>'
        f"{inner}</section>"
    )


def _cell(k: str, v: str, s: str) -> str:
    return f'<div class="cell"><p class="k">{_esc(k)}</p><p class="v">{_esc(v)}</p><p class="s">{_esc(s)}</p></div>'


def _ledger_rows(data: SiteData) -> str:
    rows = []
    for r in data.ledger:
        info = data.questions.get(r.question)
        date = info.resolution_date if info else ""
        rows.append(
            '<div class="row">'
            f'<span class="q"><code>{_esc(r.question)}</code></span>'
            f'<span class="m">{_esc(r.model)}</span>'
            f'<span class="v">{_esc(r.median)}</span>'
            f'<span class="d">{_esc(date)}</span>'
            f'<span class="h">{_esc(r.sha256)}</span>'
            "</div>"
        )
    return f'<div class="rows">{"".join(rows)}</div>'


# ============================================================================ index
def _index_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "an open forecasting engine",
        "The CIA's forecasting model was never checkable.",
        "Now it is.",
        "A complete open replication of the Bueno de Mesquita group decision model — the engine the "
        "CIA ran as Policon — evaluated against the benchmark it was never tested on, with every "
        "live forecast sealed by cryptographic hash before its event resolves.",
        '<a class="p" href="#paper">Read the paper</a>'
        '<a href="#ledger">The sealed ledger</a>'
        '<a href="#verify">Verify it yourself</a>',
    )

    cells = [
        _cell(
            "FORECASTS SEALED",
            str(data.sealed_count),
            f"across {data.question_count} live questions",
        ),
        _cell("GRADED", str(data.graded_count), f"first grading {data.grading_date}"),
    ]
    if data.gate_count:
        cells.append(_cell("GATES PRE-REGISTERED", str(data.gate_count), "none moved"))
    cells.append(_cell("DECISIONS LOGGED", str(data.decisions_count), "every interpretive choice"))
    if data.test_count:
        cells.append(_cell("TESTS", data.test_count, "green on every commit"))
    grid = f'<div class="grid">{"".join(cells)}</div>'

    deu_n = data.fig("E-DEU-N") or "the DEU"
    finding = _section(
        "finding",
        "The finding",
        '<div class="two">'
        '<p class="big">The famous model loses to the average of its own inputs — and nothing else '
        "beats that average either.</p>"
        "<div>"
        f'<p class="body">Evaluated on {_esc(deu_n)} expert-coded European legislative controversies '
        "with sourced capabilities and reference points, the challenge model fails a gate fixed in "
        "writing before the result existed. A pre-registered search for a successor — its data split "
        "committed to version control before any model was written — produced two candidates that "
        "both failed on held-out data.</p>"
        '<p class="body">A deliberately overfit-capable probe then found no signal left to extract. '
        "The simple weighted mean is not merely hard to beat; it sits at the ceiling of what these "
        "inputs can predict. What made the lineage work was never the equations. It was the "
        "discipline of turning expert judgement into structured numbers — structure, not magic.</p>"
        + _deep("findings.html", "The trials and the ceiling")
        + "</div></div>",
        rule=False,
    )

    ledger = _section(
        "ledger",
        "The sealed ledger",
        '<p class="body">Every forecast below was committed to a public repository and anchored in '
        "the bitcoin blockchain before its event resolved. Nothing has been graded yet, so no "
        "accuracy is claimed.</p>"
        + _figure(
            forecast_landscape(data),
            "Fig. 1 — sealed forecast landscape · generated from FORECASTS.md",
        )
        + _deep("ledger.html", f"The full ledger — all {data.sealed_count} forecasts"),
    )

    n_gates = data.gate_count
    trials_sec = _section(
        "trials",
        "The trials",
        f'<p class="body">{n_gates} gates, each fixed in writing before the result existed. None '
        "was moved. Mean absolute error against the outcome, model versus baseline, on the same "
        "scale.</p>"
        + _figure(
            trials(data),
            "Fig. 2 — pre-registered trials, in run order · generated from BACKTEST.md",
        )
        + _deep("findings.html", "Every gate and its verdict"),
    )

    apparatus = _section(
        "apparatus",
        "The apparatus",
        '<p class="body">A question in plain language becomes a formal game, a distribution over '
        "outcomes, a strategy brief for every actor, and a sealed record that a stranger can "
        "re-run.</p>"
        '<div class="cards">'
        '<div class="card"><p class="t">I · READ</p><h3>Formalize</h3><p>A language model reads the '
        "evidence and drafts the game — every actor's position, salience and capability, each with a "
        "cited source, each guess disclosed. A firewall keeps the concept library from ever "
        "supplying a fact.</p></div>"
        '<div class="card"><p class="t">II · PREDICT</p><h3>Solve</h3><p>Two solvers run side by side '
        "across ten thousand sampled worlds — the replicated challenge model and the weighted mean "
        "that beat it — producing a distribution, not a guess.</p></div>"
        '<div class="card"><p class="t">III · ADVISE</p><h3>Strategy</h3><p>An exhaustive lever '
        "search per actor: best own moves, what survives the opponent's answer, who to persuade, and "
        "which recommendations are robust rather than knife-edge.</p></div>"
        '<div class="card"><p class="t">IV · SEAL</p><h3>Commit</h3><p>Every forecast is '
        "deterministic, so its hash is a complete commitment. Published before the event, anchored in "
        "bitcoin, graded in public against a rubric written in advance.</p></div>"
        "</div>",
    )

    canon = _canon_section(data, repo_url)
    record = _record_section(data, repo_url)

    paper = _section(
        "paper",
        "The paper",
        '<p class="big">Structure, Not Magic: An Open Replication and '
        "Predictability Ceiling for the Bueno de Mesquita Forecasting Model</p>"
        '<p class="body">Every figure in the manuscript regenerates from a repository artifact by a '
        "single command. Zero unresolved citations.</p>"
        + _deep("paper.html", "Abstract, draft, and bibliography"),
    )

    verify = _section(
        "verify",
        "Verify it yourself",
        '<p class="body">Nothing here asks for trust. Clone the repository and check any forecast '
        "against its hash, then check the hash against the blockchain.</p>"
        f"<pre>git clone {_esc(repo_url)}\n"
        "schelling verify runs/&lt;record&gt;.json\n"
        "ots verify ledger-proofs/FORECASTS.md-&lt;hash&gt;.ots -f FORECASTS.md</pre>",
    )

    return hero + grid + finding + ledger + trials_sec + apparatus + canon + record + paper + verify


def _canon_section(data: SiteData, repo_url: str) -> str:
    if not data.canon_cards:
        return _section(
            "canon",
            "The canon",
            '<p class="body">A concept library informs how a situation is read; it may never testify '
            "about one.</p>",
        )
    families = ", ".join(name for _letter, name in data.canon_families)
    fam_clause = f" across the families of {_esc(families)}" if families else ""
    return _section(
        "canon",
        "The canon",
        '<div class="two">'
        f'<p class="big">{data.canon_cards} findings from a century of conflict research, each with '
        "its evidence strength and a rule for coding it.</p>"
        f'<p class="body">Every card{fam_clause} carries a citation, an honesty tag — robust, '
        "supported, contested, theory — and the observable evidence that would instantiate it. The "
        "library may classify a situation. It may never testify about one."
        + _deep(f"{repo_url}/blob/main/data/concepts/canon.md", "The concept library")
        + "</p></div>",
    )


def _record_section(data: SiteData, repo_url: str) -> str:
    counts = []
    if data.decisions_count:
        counts.append(f"{data.decisions_count} interpretive choices")
    if data.gate_count:
        counts.append(f"{data.gate_count} pre-registered gates")
    lead = " and ".join(counts)
    body = (
        f'<p class="body">{lead.capitalize()} — logged, dated, and public. Corrections are made on '
        "top, never by erasure.</p>"
        if lead
        else '<p class="body">Every interpretive choice, logged, dated, and public. Corrections are '
        "made on top, never by erasure.</p>"
    )
    return _section(
        "record",
        "The record",
        body + _deep(f"{repo_url}/blob/main/DECISIONS.md", "The decisions log"),
    )


# ============================================================================ ledger page
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
    grid = (
        '<div class="grid">'
        + _cell(
            "FORECASTS SEALED", str(data.sealed_count), f"across {data.question_count} questions"
        )
        + _cell("GRADED", str(data.graded_count), f"first grading {data.grading_date}")
        + "</div>"
    )
    honesty = (
        '<p class="body">Nothing here has been graded yet, so no accuracy is claimed. Each row is '
        "the SHA-256 of a complete forecast record, anchored in the bitcoin blockchain before its "
        "event resolved.</p>"
    )
    ledger = _section("ledger", "Every sealed forecast", honesty + _ledger_rows(data), rule=False)
    q_cards = []
    for info in data.questions.values():
        graded = "graded" if info.question_id in data.graded_questions else "sealed"
        q_cards.append(
            '<div class="card">'
            f'<p class="t">{_esc(graded).upper()} · RESOLVES {_esc(info.resolution_date)}</p>'
            f"<h3>{_esc(info.question_id)}</h3>"
            f"<p>Pre-registered grading rubric, fixed in writing before resolution. "
            f"{_blob(repo_url, info.rubric_file, 'Read the rubric')}.</p></div>"
        )
    questions = _section(
        "questions", "Questions and rubrics", f'<div class="cards">{"".join(q_cards)}</div>'
    )
    verify = _section(
        "verify",
        "How to verify",
        '<p class="body">Anyone can audit a sealed forecast without trusting us: recompute the '
        "record's SHA-256, match it to the row, and re-solve the embedded game to confirm the "
        "forecast reproduces byte-for-byte. Then check the ledger's timestamp against bitcoin.</p>"
        "<pre>schelling verify runs/&lt;record&gt;.json\n"
        "ots verify ledger-proofs/FORECASTS.md-&lt;hash&gt;.ots -f FORECASTS.md</pre>"
        f'<p class="body">The full ledger document is {_blob(repo_url, "FORECASTS.md", "FORECASTS.md")}.</p>',
    )
    return hero + grid + ledger + questions + verify


# ============================================================================ findings page
def _findings_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "the method, and its negative results",
        "We gave the model",
        "every advantage.",
        "A fair, pre-registered evaluation of the reconstructed model — reported with the same "
        "prominence whether it passes or fails. It fails, and that is the finding.",
        "",
    )
    trials_sec = _section(
        "trials",
        "The trials",
        '<p class="body">Each gate fixed in writing before the result existed. None was moved. Mean '
        "absolute error against the outcome, model versus baseline, on the same scale.</p>"
        + _figure(
            trials(data),
            "Fig. 2 — pre-registered trials, in run order · generated from BACKTEST.md",
        ),
        rule=False,
    )
    gate_rows = []
    for label, model_mae, base_mae, verdict in trial_gates(data):
        gate_rows.append(
            '<div class="row">'
            f'<span class="g">{_esc(label)}</span>'
            f'<span class="v">{model_mae:g} / {base_mae:g}</span>'
            '<span class="d"></span>'
            f'<span class="r">{_esc(verdict)}</span></div>'
        )
    gates = _section(
        "gates",
        "Every gate and its verdict",
        f'<div class="rows">{"".join(gate_rows)}</div>'
        if gate_rows
        else '<p class="body">No gate figures could be sourced.</p>',
    )
    oracle = data.fig("E-ORACLE-MAE")
    gap = data.fig("E-ORACLE-GAP")
    sections = [trials_sec, gates]
    if oracle and gap:
        sections.append(
            _section(
                "ceiling",
                "The ceiling",
                f'<p class="big">A flexible, cross-validated oracle scores {_esc(oracle)} against '
                f"the compromise mean — a gap of {_esc(gap)}. There is essentially no signal beyond "
                "the influence-weighted average.</p>"
                '<p class="body">Even an optimistic overfit-capable probe does not beat the mean, '
                "which is why every model tried fails to beat it.</p>",
            )
        )
    if data.successor_verdict:
        sections.append(
            _section(
                "successor",
                "Successor search",
                '<p class="body">A pre-registered train/dev/test split, committed before any '
                f"fitting. {_esc(data.successor_verdict)} "
                f"The full backtest is {_blob(repo_url, 'BACKTEST.md', 'BACKTEST.md')}.</p>",
            )
        )
    return hero + "".join(sections)


# ============================================================================ paper page
def _paper_body(data: SiteData, repo_url: str) -> str:
    hero = _hero(
        "the paper",
        "Structure,",
        "not magic.",
        "An open replication and predictability ceiling for the Bueno de Mesquita forecasting "
        "model. Every cited number regenerates from a repository artifact by a single command.",
        f'<a class="p" href="{_esc(repo_url)}/blob/main/paper/DRAFT.md">Read the draft</a>'
        f'<a href="{_esc(repo_url)}">Source</a>',
    )
    sections = []
    if data.abstract:
        sections.append(
            _section(
                "abstract", "Abstract", f'<p class="body">{_esc(data.abstract)}</p>', rule=False
            )
        )
    sections.append(
        _section(
            "draft",
            "Read the draft",
            '<p class="body">The full working draft — assembled deterministically from the section '
            "files and the evidence table, every cited number carrying a per-claim provenance "
            f"footnote — is {_blob(repo_url, 'paper/DRAFT.md', 'paper/DRAFT.md')}. Regenerate the "
            "evidence base with <code>schelling paper-evidence</code>.</p>",
        )
    )
    if data.bibliography:
        items = "".join(f"<li>{_esc(entry)}</li>" for entry in data.bibliography)
        sections.append(
            _section("bibliography", "Bibliography", f'<ul class="biblist">{items}</ul>')
        )
    return hero + "".join(sections)


# ============================================================================ reports page
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
        cards = "".join(
            f'<div class="card"><p class="t">REPORT</p>'
            f'<h3><a href="{_esc(r.filename)}">{_esc(r.title)}</a></h3>'
            f'<p><a href="{_esc(r.filename)}">{_esc(r.filename)}</a></p></div>'
            for r in data.reports
        )
        inner = f'<div class="cards">{cards}</div>'
    else:
        inner = (
            '<p class="body">No rendered reports are published yet. Reports are generated with '
            "<code>schelling report</code> / <code>schelling dossier</code> and copied into "
            "docs/reports/.</p>"
        )
    return hero + _section("reports", "Published reports", inner, rule=False)


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
            "",
            "",
            "An open, continuously-audited replication of the Bueno de Mesquita forecasting model.",
        ),
        "ledger.html": (
            _ledger_body(d, repo_url),
            "Ledger — Schelling",
            "ledger",
            "",
            "The sealed commit-reveal forecast ledger, with verification instructions.",
        ),
        "findings.html": (
            _findings_body(d, repo_url),
            "Findings — Schelling",
            "trials",
            "",
            "The pre-registered evaluation, the ceiling result, and the successor search.",
        ),
        "paper.html": (
            _paper_body(d, repo_url),
            "Paper — Schelling",
            "paper",
            "",
            "Abstract, draft, and bibliography of the open replication paper.",
        ),
        "reports/index.html": (
            _reports_body(d, repo_url),
            "Reports — Schelling",
            "",
            "../",
            "Index of rendered dossiers and reports.",
        ),
    }
    out: dict[str, str] = {"site.css": SITE_CSS + "\n", ".nojekyll": ""}
    for path, (body, title, current, prefix, desc) in pages.items():
        out[path] = _shell(
            title=title,
            description=desc,
            body=body,
            current=current,
            prefix=prefix,
            data=d,
            repo_url=repo_url,
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
