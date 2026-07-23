"""Render the static site from :class:`SiteData` and diff it against the committed pages (D31).

Every page is plain, self-contained HTML linking one relative stylesheet (``site.css``); the only
external references are navigational ``<a href>`` links to the public repo (rubrics, the draft,
DOIs) — never embedded resources, so each page renders fully offline. No figure is written by hand:
the page builders interpolate only fields of :class:`SiteData`, which are parsed from artifacts.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from schelling.site.css import SITE_CSS
from schelling.site.data import SiteData, gather

DEFAULT_REPO_URL = "https://github.com/hamzagul07/schelling"

_PAGES = [
    ("index.html", "The thesis"),
    ("ledger.html", "Ledger"),
    ("findings.html", "Findings"),
    ("paper.html", "Paper"),
    ("reports/index.html", "Reports"),
]
_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _first_num(text: str) -> str:
    m = _NUM.search(text)
    return m.group(0) if m else ""


def _blob(repo_url: str, path: str, text: str) -> str:
    """A navigational link to a repository file (rubrics, DRAFT.md — they live above ``docs/`` and
    are not served by Pages, so they are linked at the public repo, not relatively)."""
    return f'<a href="{_esc(repo_url)}/blob/main/{_esc(path)}">{_esc(text)}</a>'


def _nav(current: str, prefix: str) -> str:
    links = [f'<a class="brand" href="{prefix}index.html">Schelling</a>']
    for href, label in _PAGES:
        target = prefix + (
            href[: -len("index.html")] if href.endswith("reports/index.html") else href
        )
        cur = ' aria-current="page"' if label == current else ""
        links.append(f'<a href="{target}"{cur}>{_esc(label)}</a>')
    return '<nav class="top">' + "".join(links) + "</nav>"


def _shell(
    *, title: str, description: str, current: str, body: str, data: SiteData, prefix: str
) -> str:
    footer = (
        '<footer class="page">'
        f"<span>Schelling · an open, continuously-audited forecasting engine</span>"
        f"<span>{data.decisions_count} decisions logged · {_esc(data.test_count)} tests</span>"
        "<span>every figure regenerates from repository artifacts — no number is hand-typed</span>"
        "</footer>"
    )
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="description" content="{_esc(description)}">'
        f"<title>{_esc(title)}</title>"
        f'<link rel="stylesheet" href="{prefix}site.css">'
        "</head><body>"
        f"{_nav(current, prefix)}"
        f'<main class="wrap">{body}</main>'
        f"{footer}"
        "</body></html>"
    )


def _honesty_banner(data: SiteData) -> str:
    graded = data.graded_count
    claim = (
        "No page on this site claims forecast accuracy: nothing is graded yet."
        if graded == 0
        else f"{graded} of {data.sealed_count} sealed forecasts are graded."
    )
    return (
        '<div class="honesty">'
        f"<b>{data.sealed_count} sealed · {graded} graded.</b> "
        f"Each forecast is sealed by SHA-256 before its event resolves and scored only after the "
        f"grading date. {claim} The first grading date is {_esc(data.grading_date)}."
        "</div>"
    )


def _ledger_table(data: SiteData, *, full: bool, repo_url: str) -> str:
    head = ["model", "vintage", "question", "frozen", "median"]
    head.append("sha256" if full else "sha256 (short)")
    if full:
        head.append("rubric")
    thead = "".join(
        f'<th class="num">{_esc(h)}</th>' if h in {"median"} else f"<th>{_esc(h)}</th>"
        for h in head
    )
    rows = []
    for r in data.ledger:
        graded = r.question in data.graded_questions
        chip = (
            '<span class="chip pass">graded</span>'
            if graded
            else '<span class="chip sealed">sealed</span>'
        )
        cells = [
            f"<td>{_esc(r.model)}</td>",
            f"<td>{_esc(r.vintage)}</td>",
            f"<td>{_esc(r.question)} {chip}</td>",
            f"<td>{_esc(r.frozen_at)}</td>",
            f'<td class="num">{_esc(r.median)}</td>',
        ]
        if full:
            cells.append(f'<td class="hash">{_esc(r.sha256)}</td>')
            rubric = data.questions.get(r.question)
            link = _blob(repo_url, rubric.rubric_file, "rubric") if rubric else ""
            cells.append(f"<td>{link}</td>")
        else:
            cells.append(f'<td class="hash">{_esc(r.sha256[:12])}…</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="tbl-scroll"><table><thead><tr>'
        + thead
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


# --------------------------------------------------------------------------- index
def _index_body(data: SiteData, repo_url: str) -> str:
    deu_n = data.fig("E-DEU-N") or "the DEU"
    ch = _first_num(data.fig("E-METHOD-challenge_rp"))
    comp = _first_num(data.fig("E-METHOD-baseline_wmean"))
    gap = data.fig("E-ORACLE-GAP")
    repl = data.fig("E-REPL-MEDIAN")
    gate = data.gate_verdict or "the gate"

    finding = (
        '<div class="finding">'
        f"On <b>{_esc(deu_n)}</b> expert-coded EU legislative decisions, the reconstructed "
        f"Bueno de Mesquita challenge model scores a mean absolute error of <b>{_esc(ch)}</b> and "
        f"loses a pre-registered accuracy gate to a far simpler benchmark — the capability-and-"
        f"salience-weighted mean, at <b>{_esc(comp)}</b>. "
        f"A deliberately flexible cross-validated oracle then posts a ceiling gap of "
        f"<b>{_esc(gap)}</b> against that mean: at or below zero, the weighted mean already sits "
        f"at the extractable-signal ceiling for this domain and input set. "
        f"The machinery was not beaten by a better model; there was no further signal to extract — "
        f"structure, not magic."
        "</div>"
    )

    movements = [
        (
            "Replication",
            f"Rebuild the model from the Scholz-Calbert-Smith reconstruction with every "
            f"interpretive choice logged, and reproduce the emission case at {_esc(repl)}.",
        ),
        (
            "The fair fight",
            f"Score it on {_esc(deu_n)} expert-coded EU decisions with sourced capabilities and "
            f"reference points against a gate fixed in advance — it fails ({_esc(gate)}).",
        ),
        (
            "The successor search",
            "Commit the train/dev/test split to version control before any fitting; two "
            "structurally-motivated successors both fail on the untouched test split.",
        ),
        (
            "The ceiling",
            f"A flexible oracle shows the simple mean is already at the extractable-signal ceiling "
            f"({_esc(gap)}). Then seal live forecasts, cryptographically, before events resolve.",
        ),
    ]
    mv_html = "".join(
        f'<li><div class="mv-t">{_esc(t)}</div><div class="mv-d">{d}</div></li>'
        for t, d in movements
    )

    counter = (
        f'<div class="counter" data-target="{_esc(data.grading_date)}">'
        f'<span class="big" data-count>—</span>'
        f'<span class="lbl">days to the first grading date ({_esc(data.grading_date)}) · '
        f"resolution {_esc(data.resolution_date)}</span></div>"
        "<script>"
        "(function(){var ns=document.querySelectorAll('.counter[data-target]');"
        "for(var i=0;i<ns.length;i++){var e=ns[i];"
        "var t=new Date(e.getAttribute('data-target')+'T00:00:00Z');"
        "var d=Math.ceil((t-new Date())/86400000);var o=e.querySelector('[data-count]');"
        "if(o)o.textContent=(d>0?d:0);}})();"
        "</script>"
    )

    verify = (
        "<pre># recompute a sealed record's hash and re-solve it deterministically\n"
        "schelling verify runs/&lt;record&gt;.json\n\n"
        "# or, by hand, and match the digest against the ledger row\n"
        "sha256sum runs/&lt;record&gt;.json</pre>"
    )

    return (
        '<header class="page">'
        '<p class="kicker">An open, continuously-audited forecasting engine</p>'
        "<h1>Structure, not magic.</h1>"
        '<p class="thesis">A bounded geopolitical question becomes a formal bargaining game, a '
        "deterministic solution, and a probability forecast — with a complete audit trail.</p>"
        '<p class="dek">Every probability is computed, never guessed by a model. Every run is '
        "seeded and reproducible. Every live forecast is sealed before the event resolves.</p>"
        "</header>"
        "<h2>The finding, in three sentences</h2>"
        + finding
        + '<h2>Four movements</h2><ol class="movements">'
        + mv_html
        + "</ol>"
        + "<h2>The live ledger</h2>"
        + counter
        + _honesty_banner(data)
        + _ledger_table(data, full=False, repo_url=repo_url)
        + '<p class="note">The full table, with complete hashes and per-question rubrics, is on '
        'the <a href="ledger.html">ledger</a> page.</p>'
        + "<h2>How to verify</h2>"
        + "<p>Anyone can audit a sealed forecast without trusting us. The record files are "
        "gitignored (commit-reveal), so no number can be edited after the fact; reveal and check "
        "locally:</p>"
        + verify
        + '<p class="note">Full verification — including the OpenTimestamps Bitcoin anchor — is on '
        'the <a href="ledger.html">ledger</a> page. The method and its negative results are on '
        '<a href="findings.html">findings</a>.</p>'
    )


# --------------------------------------------------------------------------- ledger
def _ledger_body(data: SiteData, repo_url: str) -> str:
    proof = "ledger-proofs/FORECASTS.md-&lt;sha12&gt;.ots"
    verify = (
        "<h3>Recompute-and-match</h3>"
        "<pre>schelling verify runs/&lt;record&gt;.json</pre>"
        "<p>Recomputes the record file's SHA-256 and matches it to the row below, recomputes the "
        "canonical inputs hash, and re-solves the embedded game with the record's own seed to "
        "confirm the forecast reproduces byte-for-byte. Equivalently by hand:</p>"
        "<pre>sha256sum runs/&lt;record&gt;.json</pre>"
        "<h3>External time anchor (OpenTimestamps)</h3>"
        "<pre>ots verify " + proof + " -f FORECASTS.md</pre>"
        "<p>Each seal timestamps the ledger; the proofs live in "
        '<span class="mono">ledger-proofs/</span>, content-addressed by the ledger\'s SHA-256. A '
        'Bitcoin-anchored timestamp cannot be backdated — run <code class="inl">ots upgrade</code> '
        "first once the attestation has confirmed.</p>"
    )
    q_lines = []
    for info in data.questions.values():
        graded = info.question_id in data.graded_questions
        chip = (
            '<span class="chip pass">graded</span>'
            if graded
            else '<span class="chip pending">awaiting resolution</span>'
        )
        q_lines.append(
            f"<li>{_blob(repo_url, info.rubric_file, info.question_id)} — resolves "
            f"{_esc(info.resolution_date)} {chip}</li>"
        )
    return (
        '<header class="page">'
        '<p class="kicker">The sealed forecast ledger</p>'
        "<h1>Ledger</h1>"
        '<p class="dek">Commit-reveal: each forecast is sealed by the SHA-256 of its run record '
        "before the event resolves. The record files are gitignored, so no number can be quietly "
        "edited after the outcome is known.</p></header>"
        + _honesty_banner(data)
        + _ledger_table(data, full=True, repo_url=repo_url)
        + '<h2>Questions &amp; pre-registered rubrics</h2><ul class="reports">'
        + "".join(q_lines)
        + "</ul>"
        + "<h2>Independent verification</h2>"
        + verify
        + '<p class="note">The full ledger document, with the hash-basis and anchoring '
        f"corrections stated in the open, is {_blob(repo_url, 'FORECASTS.md', 'FORECASTS.md')}.</p>"
    )


# --------------------------------------------------------------------------- findings
def _findings_body(data: SiteData, repo_url: str) -> str:
    ch = data.fig("E-METHOD-challenge_rp")
    comp = data.fig("E-METHOD-baseline_wmean")
    med = data.fig("E-METHOD-baseline_median")
    oracle = data.fig("E-ORACLE-MAE")
    gap = data.fig("E-ORACLE-GAP")
    gate = data.gate_verdict or ""
    gate_chip = f'<span class="chip fail">{_esc(gate)}</span>' if gate == "FAILED" else _esc(gate)

    # successor leaderboard, reproduced from the BACKTEST.md marker block
    if data.leaderboard_rows:
        thead = "".join(f"<th>{_esc(h)}</th>" for h in data.leaderboard_header)
        body = "".join(
            "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in cells) + "</tr>"
            for cells in data.leaderboard_rows
        )
        leaderboard = (
            '<div class="tbl-scroll"><table><thead><tr>'
            + thead
            + "</tr></thead><tbody>"
            + body
            + "</tbody></table></div>"
        )
    else:
        leaderboard = "<p>(leaderboard unavailable)</p>"

    gates = (
        '<ul class="reports">'
        f"<li><b>Gate v2 — fair fight.</b> The fully-equipped challenge solver must beat the "
        f"equally-equipped weighted mean on DEU MAE. Verdict: {gate_chip} "
        f"(challenge {_esc(ch)} vs mean {_esc(comp)}; median baseline {_esc(med)}).</li>"
        f"<li><b>Successor gate.</b> Each candidate must beat the compromise mean on the "
        f'untouched TEST split. Verdict: <span class="chip fail">no candidate beats the mean</span>'
        f".</li>"
        f"<li><b>Ceiling diagnostic.</b> A flexible cross-validated oracle scores {_esc(oracle)}; "
        f"the gap to the mean is {_esc(gap)} — at or below zero places the mean at the "
        f'extractable-signal ceiling. <span class="chip">cooperative domain only</span></li>'
        "</ul>"
    )
    return (
        '<header class="page">'
        '<p class="kicker">The method, and its negative results</p>'
        "<h1>Findings</h1>"
        '<p class="dek">A fair, pre-registered evaluation of the reconstructed model — reported '
        "with the same prominence whether it passes or fails. It fails, and that is the finding."
        "</p></header>"
        "<h2>Pre-registered gates &amp; verdicts</h2>"
        + gates
        + "<h2>The ceiling</h2>"
        + f'<p class="lead">The oracle model — deliberately flexible, cross-validated — scores '
        f"{_esc(oracle)} against the compromise mean, a gap of {_esc(gap)}. Even an optimistic "
        f"flexible model does not beat the mean: there is essentially no signal beyond the "
        f"influence-weighted average, which is why every model tried fails to beat it.</p>"
        + "<h2>Successor-search leaderboard</h2>"
        + leaderboard
        + (f'<p class="note">{_esc(data.successor_verdict)}</p>' if data.successor_verdict else "")
        + '<p class="note">The full backtest — per-method errors, worst issues, published-model '
        f"context, and domain verdicts — is {_blob(repo_url, 'BACKTEST.md', 'BACKTEST.md')}.</p>"
    )


# --------------------------------------------------------------------------- paper
def _paper_body(data: SiteData, repo_url: str) -> str:
    bib = "".join(f"<li>{_esc(entry)}</li>" for entry in data.bibliography)
    abstract = data.abstract or "(abstract unavailable)"
    return (
        '<header class="page">'
        '<p class="kicker">The paper</p>'
        "<h1>Structure, Not Magic</h1>"
        '<p class="thesis">An open replication and predictability ceiling for the Bueno de '
        "Mesquita forecasting model.</p></header>"
        "<h2>Abstract</h2>"
        f'<p class="lead">{_esc(abstract)}</p>'
        "<h2>Read the draft</h2>"
        f"<p>The full working draft — assembled deterministically from the section files and "
        f"the evidence table, every cited number carrying a per-claim provenance footnote — is "
        f"{_blob(repo_url, 'paper/DRAFT.md', 'paper/DRAFT.md')}. Every figure it cites regenerates "
        f"from repository artifacts by a single command "
        f'(<code class="inl">schelling paper-evidence</code>).</p>'
        "<h2>Bibliography</h2>"
        f'<ul class="bib">{bib}</ul>'
    )


# --------------------------------------------------------------------------- reports
def _reports_body(data: SiteData, repo_url: str) -> str:
    if data.reports:
        items = "".join(
            f'<li><a href="{_esc(r.filename)}">{_esc(r.title)}</a>'
            f'<span class="rf">{_esc(r.filename)}</span></li>'
            for r in data.reports
        )
        listing = f'<ul class="reports">{items}</ul>'
    else:
        listing = (
            '<p class="note">No rendered reports are published yet. Reports are generated with '
            '<code class="inl">schelling report</code> / <code class="inl">schelling dossier</code>'
            ' and copied into <span class="mono">docs/reports/</span>.</p>'
        )
    return (
        '<header class="page">'
        '<p class="kicker">Rendered dossiers &amp; reports</p>'
        "<h1>Reports</h1>"
        '<p class="dek">Two-audience reports and research dossiers rendered from sealed run '
        "records. Each is self-contained HTML with inline figures — open one directly.</p></header>"
        + listing
    )


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
            "The thesis",
            "The thesis",
            "",
            "Schelling — an open, continuously-audited strategic forecasting engine",
        ),
        "ledger.html": (
            _ledger_body(d, repo_url),
            "Ledger — Schelling",
            "Ledger",
            "",
            "The sealed commit-reveal forecast ledger, with verification instructions",
        ),
        "findings.html": (
            _findings_body(d, repo_url),
            "Findings — Schelling",
            "Findings",
            "",
            "The pre-registered evaluation, the ceiling result, and the backtest leaderboard",
        ),
        "paper.html": (
            _paper_body(d, repo_url),
            "Paper — Schelling",
            "Paper",
            "",
            "Abstract, draft, and bibliography of the open replication paper",
        ),
        "reports/index.html": (
            _reports_body(d, repo_url),
            "Reports — Schelling",
            "Reports",
            "../",
            "Index of rendered dossiers and reports",
        ),
    }
    out: dict[str, str] = {"site.css": SITE_CSS + "\n", ".nojekyll": ""}
    for path, (body, title, current, prefix, desc) in pages.items():
        out[path] = _shell(
            title=title, description=desc, current=current, body=body, data=d, prefix=prefix
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
