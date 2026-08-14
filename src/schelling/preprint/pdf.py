"""Render the preprint manuscript to PDF (Session 55, D55).

``manuscript.md`` -> HTML (pandoc, for footnote/heading lexing) -> footnote merge/renumber -> PDF
(WeasyPrint, ``@page`` running header + page numbers). The four figures are inlined as raw
``<figure>`` SVG so the PDF is self-contained (no external image refs, no broken links) and each
caption appears once.

Toolchain (see ``paper/preprint/README.md``): the ``pandoc`` binary on PATH, and WeasyPrint with its
system libraries (pango, cairo). Neither is a hard dependency of the package — they are checked with
friendly errors, so CI (which builds no PDF) stays light.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from schelling.dossier.pdf import html_to_pdf, weasyprint_available

_FIGURES = (
    "fig_deu_error_histogram.svg",
    "fig_challenge_vs_compromise.svg",
    "fig_leaderboard.svg",
    "fig_r1_split.svg",
)

_CSS = """
@page {
  size: A4;
  margin: 22mm 20mm 18mm 20mm;
  @top-left { content: string(runhead); font-size: 8pt; color: #6b7280; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages);
    font-size: 8pt; color: #6b7280; }
}
.runhead { position: absolute; left: -9999px; top: 0; string-set: runhead content(); }
body { font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.5;
  color: #14181f; }
h1 { font-size: 19pt; line-height: 1.22; margin: 0 0 6px; letter-spacing: -0.01em; }
h1 + p { margin-top: 4px; }                    /* author block hugs the title */
h2 { font-size: 12.5pt; margin: 20px 0 7px; padding-bottom: 3px;
  border-bottom: 1px solid #d7dbe0; break-after: avoid; }
h3 { font-size: 11pt; margin: 14px 0 5px; break-after: avoid; }
p { margin: 6px 0; text-align: justify; hyphens: auto; }
a { color: #0f766e; text-decoration: none; word-break: break-word; }
strong { color: #0b0e13; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 8.7pt;
  background: #f3f4f6; padding: 0 2px; border-radius: 3px; }
figure.fig { margin: 16px 0; text-align: center; break-inside: avoid; }
figure.fig svg { max-width: 82%; height: auto; }
figcaption { font-size: 8.6pt; color: #4b5563; font-style: italic; margin-top: 5px;
  max-width: 90%; margin-left: auto; margin-right: auto; }
table { border-collapse: collapse; font-size: 9pt; margin: 10px 0; width: 100%;
  break-inside: avoid; }
th, td { border: 1px solid #d7dbe0; padding: 3px 6px; text-align: left; }
hr { border: 0; border-top: 1px solid #ccd; margin: 22px 0 8px; }
.footnotes { font-size: 8.4pt; color: #374151; }
.footnotes hr { display: none; }
.footnotes ol { padding-left: 16px; }
.footnotes li { margin: 2px 0; }
"""


def pandoc_available() -> bool:
    """True when the ``pandoc`` binary is on PATH."""
    return shutil.which("pandoc") is not None


def reuse_footnotes(html: str) -> str:
    """Merge pandoc's duplicate footnotes so a repeated citation REUSES its number (D54/D55).

    Pandoc renders each reference to a re-used ``[^id]`` as a fresh, duplicate numbered note. We
    group the notes by content, keep the first of each, renumber them 1..K, and rewrite every body
    reference to point at — and display — its note's canonical number. A no-footnote document is
    returned unchanged.
    """
    m = re.search(r'(<section id="footnotes".*?<ol>)(.*?)(</ol>\s*</section>)', html, re.S)
    if not m:
        return html
    head, ol_body, tail = m.groups()
    items = re.findall(r'<li id="fn(\d+)">(.*?)</li>', ol_body, re.S)

    def _content(inner: str) -> str:  # the note text without its back-reference arrow
        return re.sub(r'<a href="#fnref\d+"[^>]*>.*?</a>', "", inner, flags=re.S).strip()

    canon: dict[str, int] = {}
    old_to_new: dict[int, int] = {}
    kept: list[tuple[int, str]] = []
    for old, inner in items:
        key = _content(inner)
        if key not in canon:
            canon[key] = len(canon) + 1
            kept.append((canon[key], inner))
        old_to_new[int(old)] = canon[key]

    new_lis = "\n".join(f'<li id="fn{n}">{inner}</li>' for n, inner in kept)
    html = html[: m.start()] + head + "\n" + new_lis + "\n" + tail + html[m.end() :]

    def _fix_ref(rm: re.Match[str]) -> str:
        old = int(rm.group("num"))
        new = old_to_new.get(old, old)
        fixed = rm.group(0).replace(f'href="#fn{old}"', f'href="#fn{new}"')
        return re.sub(r"<sup>\d+</sup>", f"<sup>{new}</sup>", fixed)

    return re.sub(
        r'<a href="#fn(?P<num>\d+)" class="footnote-ref"[^>]*><sup>\d+</sup></a>', _fix_ref, html
    )


def inline_figures(md: str, figures_dir: Path, figures: tuple[str, ...] = _FIGURES) -> str:
    """Replace each ``![cap](figures/x.svg)`` + ``*cap*`` pair with a self-contained ``<figure>``.

    Raises ``ValueError`` if a figure is not referenced exactly once (the manuscript is malformed).
    """
    for fname in figures:
        svg = (figures_dir / fname).read_text()
        svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.S)
        svg = re.sub(r"<!DOCTYPE.*?>", "", svg, flags=re.S).strip()
        pat = re.compile(
            r"!\[(?P<cap>[^\]]*)\]\(figures/" + re.escape(fname) + r"\)\s*\n\s*\n\*[^\n]*\*"
        )

        def _repl(rm: re.Match[str], _svg: str = svg) -> str:
            cap = rm.group("cap")
            return f'<figure class="fig">\n{_svg}\n<figcaption>{cap}</figcaption>\n</figure>'

        md, n = pat.subn(_repl, md)
        if n != 1:
            raise ValueError(f"figure {fname}: expected exactly one reference, got {n}")
    return md


def markdown_to_html(md: str) -> str:
    """pandoc markdown -> HTML body with duplicate footnotes merged (raises if pandoc is absent)."""
    if not pandoc_available():
        raise RuntimeError(
            "the preprint PDF build needs the `pandoc` binary on PATH (`brew install pandoc`); "
            "see paper/preprint/README.md"
        )
    proc = subprocess.run(
        ["pandoc", "-f", "markdown-implicit_figures", "-t", "html5", "--wrap=none"],
        input=md,
        capture_output=True,
        text=True,
        check=True,
    )
    return reuse_footnotes(proc.stdout)


def wrap_html(body: str, *, runhead: str) -> str:
    """Wrap a pandoc HTML body in the paginated preprint document (``@page`` header + numbers)."""
    return (
        "<html><head><meta charset='utf-8'><style>"
        + _CSS
        + "</style></head><body><div class='runhead'>"
        + runhead
        + "</div>"
        + body
        + "</body></html>"
    )


def build_pdf(manuscript_md: str, figures_dir: Path, out_path: Path, *, runhead: str) -> None:
    """Build the preprint PDF from the manuscript markdown and its figures directory.

    Raises ``RuntimeError`` (with an install hint) if WeasyPrint or pandoc is unavailable.
    """
    if not weasyprint_available():
        raise RuntimeError(
            "the preprint PDF build needs WeasyPrint and its system libraries (pango, cairo): "
            "`brew install pango` then `uv pip install weasyprint` — see paper/preprint/README.md"
        )
    body = markdown_to_html(inline_figures(manuscript_md, figures_dir))
    html_to_pdf(wrap_html(body, runhead=runhead), out_path)
