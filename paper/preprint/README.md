# Preprint build

The SSRN preprint (`manuscript.md` + `manuscript.pdf` in this directory) is built from the assembled
paper by one command:

```bash
schelling paper-assemble        # regenerate paper/DRAFT.md from the draft sections + EVIDENCE.md
schelling preprint build        # DRAFT.md + front-matter.toml -> manuscript.md + manuscript.pdf
```

`schelling preprint build --md-only` writes `manuscript.md` only and skips the PDF (no external
tools needed).

## What it does (`src/schelling/preprint/`)

1. **`manuscript.md`** — `assemble_manuscript` takes `paper/DRAFT.md`, drops the `paper-assemble`
   banner comment, and prepends a title / author / correspondence / date / **Keywords** block plus a
   one-line version note. The body (including the provenance footnotes) is the assembled paper
   verbatim, so DRAFT.md and the preprint always agree. The version-specific fields live in
   [`front-matter.toml`](front-matter.toml) — a **version bump is a config edit there, not a code
   change**.
2. **`manuscript.pdf`** — markdown → HTML (`pandoc`) → footnote **merge/renumber** → PDF
   (WeasyPrint, with an `@page` running header and page numbers). The four figures are inlined as
   raw `<figure>` SVG so the PDF is self-contained. The footnote step (`reuse_footnotes`) merges the
   duplicate notes pandoc emits for a re-referenced footnote, so a **repeated E-tag citation reuses
   its number** (Session 54/55).

## Toolchain (required for the PDF only)

The Markdown → HTML → PDF path needs two things that are **not** package dependencies (so CI, which
builds no PDF, stays light). The command checks for both and prints an install hint if either is
missing.

- **pandoc** — the Markdown→HTML lexer. Install the binary and put it on `PATH`:
  ```bash
  brew install pandoc          # macOS;  apt-get install pandoc  on Debian/Ubuntu
  ```
- **WeasyPrint + its system libraries (pango, cairo)** — the HTML→PDF renderer. WeasyPrint is a
  Python package installed into the venv only; its rendering relies on the pango/cairo/HarfBuzz
  system libraries:
  ```bash
  brew install pango           # pulls in cairo, harfbuzz, gdk-pixbuf, …  (Debian/Ubuntu:
                               # apt-get install libpango-1.0-0 libpangocairo-1.0-0 libcairo2)
  uv pip install weasyprint    # into the project venv only — NOT added to pyproject.toml
  ```
  Georgia (the body face) and Menlo (code) are used if the system provides them; otherwise
  WeasyPrint substitutes a serif / monospace fallback.

`ssrn-metadata.md` in this directory holds the SSRN submission-form fields (title, abstract,
keywords, classification) and the plain-language summary; it is not part of the build.
