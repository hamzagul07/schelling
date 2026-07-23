"""The one stylesheet (D31.4). Self-contained: system font stacks only — no external fonts, no
imports, no network. Serif for the thesis lines, sans for body, monospace for hashes and ids; one
accent colour (the reports' amber ``#b45309``); 0.5px hairlines, no gradients or shadows; a dark
mode via ``prefers-color-scheme`` and a print stylesheet."""

SITE_CSS = """
:root {
  --ink: #1f2937; --muted: #6b7280; --faint: #9ca3af;
  --line: #e5e7eb; --hair: rgba(31,41,55,.14); --panel: #f9fafb; --bg: #ffffff;
  --accent: #b45309; --accent-soft: #fff7ed;
  --serif: Georgia, Cambria, "Times New Roman", Times, serif;
  --sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e5e7eb; --muted: #9ca3af; --faint: #6b7280;
    --line: #2a2f3a; --hair: rgba(229,231,235,.16); --panel: #14171d; --bg: #0e1116;
    --accent: #f59e0b; --accent-soft: #1c1710;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.6 var(--sans); font-feature-settings: "kern";
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 760px; margin: 0 auto; padding: 0 24px 96px; }
a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--hair); }
a:hover { border-bottom-color: var(--accent); color: var(--accent); }

/* ---- top nav ---- */
nav.top {
  max-width: 760px; margin: 0 auto; padding: 22px 24px 18px;
  display: flex; flex-wrap: wrap; gap: 4px 22px; align-items: baseline;
  border-bottom: .5px solid var(--line);
}
nav.top .brand { font: 600 15px/1 var(--serif); letter-spacing: .01em; margin-right: auto; border: 0; }
nav.top a { font-size: 13px; color: var(--muted); border: 0; text-transform: lowercase; letter-spacing: .02em; }
nav.top a:hover, nav.top a[aria-current] { color: var(--accent); }

/* ---- masthead ---- */
header.page { padding: 56px 0 8px; }
.kicker { font-size: 12px; text-transform: uppercase; letter-spacing: .14em; color: var(--muted); margin: 0 0 18px; }
h1 { font: 400 30px/1.25 var(--serif); letter-spacing: -.01em; margin: 0 0 10px; }
.thesis { font: 400 21px/1.5 var(--serif); color: var(--ink); margin: 0 0 8px; }
.dek { font-size: 16px; color: var(--muted); margin: 0 0 8px; max-width: 62ch; }
h2 { font: 600 13px/1.3 var(--sans); text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
  margin: 52px 0 16px; padding-bottom: 8px; border-bottom: .5px solid var(--line); }
h3 { font: 600 16px/1.4 var(--sans); margin: 32px 0 6px; }
p { margin: 0 0 14px; }
p.lead { font-size: 17px; }

/* ---- the finding, in three sentences ---- */
.finding { font: 400 19px/1.6 var(--serif); border-left: 2px solid var(--accent); padding: 4px 0 4px 20px; margin: 8px 0 4px; }
.finding b { font-weight: 400; font-variant-numeric: tabular-nums; color: var(--accent); }

/* ---- movements ---- */
.movements { list-style: none; margin: 8px 0; padding: 0; counter-reset: mv; }
.movements li { counter-increment: mv; padding: 16px 0; border-top: .5px solid var(--line); display: grid;
  grid-template-columns: 2.4em 1fr; gap: 4px 14px; }
.movements li::before { content: counter(mv, decimal-leading-zero); font: 400 14px/1.5 var(--mono); color: var(--faint); }
.movements .mv-t { font: 600 15px/1.4 var(--sans); }
.movements .mv-d { grid-column: 2; color: var(--muted); font-size: 15px; }

/* ---- tables ---- */
.tbl-scroll { overflow-x: auto; margin: 8px 0 6px; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 9px 12px 9px 0; border-bottom: .5px solid var(--line); vertical-align: top; white-space: nowrap; }
th { font-weight: 600; color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: .06em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.mono, .mono { font-family: var(--mono); font-size: 12px; }
tbody tr:hover td { background: var(--panel); }
.hash { font-family: var(--mono); font-size: 12px; color: var(--muted); word-break: break-all; white-space: normal; }

/* ---- status chips ---- */
.chip { display: inline-block; font: 600 11px/1.6 var(--sans); text-transform: uppercase; letter-spacing: .05em;
  padding: 1px 8px; border-radius: 10px; border: 1px solid var(--hair); color: var(--muted); }
.chip.sealed { color: var(--accent); border-color: var(--accent); }
.chip.pending { color: var(--muted); }
.chip.pass { color: #065f46; border-color: #6ee7b7; background: #ecfdf5; }
.chip.fail { color: #991b1b; border-color: #fca5a5; background: #fef2f2; }
@media (prefers-color-scheme: dark) {
  .chip.pass { color: #6ee7b7; background: transparent; }
  .chip.fail { color: #fca5a5; background: transparent; }
}

/* ---- countdown ---- */
.counter { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; margin: 6px 0 2px;
  padding: 16px 0; border-top: .5px solid var(--line); border-bottom: .5px solid var(--line); }
.counter .big { font: 400 34px/1 var(--serif); font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.counter .lbl { font-size: 13px; color: var(--muted); }

/* ---- honesty banner ---- */
.honesty { background: var(--panel); border: .5px solid var(--line); border-radius: 4px; padding: 14px 16px;
  margin: 20px 0; font-size: 14px; color: var(--muted); }
.honesty b { color: var(--ink); font-weight: 600; }

/* ---- callout / verify ---- */
.note { border-left: 2px solid var(--hair); padding-left: 18px; color: var(--muted); font-size: 15px; margin: 16px 0; }
code, pre { font-family: var(--mono); font-size: 13px; }
pre { background: var(--panel); border: .5px solid var(--line); border-radius: 4px; padding: 14px 16px;
  overflow-x: auto; line-height: 1.55; color: var(--ink); }
code.inl { background: var(--panel); border: .5px solid var(--line); border-radius: 3px; padding: 1px 5px; }

/* ---- report index ---- */
.reports { list-style: none; margin: 8px 0; padding: 0; }
.reports li { padding: 14px 0; border-top: .5px solid var(--line); }
.reports a { border: 0; font-weight: 600; }
.reports .rf { font-family: var(--mono); font-size: 12px; color: var(--faint); display: block; margin-top: 2px; }

/* ---- bibliography ---- */
.bib { list-style: none; margin: 8px 0; padding: 0; }
.bib li { font-size: 14px; color: var(--ink); padding: 8px 0 8px 22px; text-indent: -22px; border-bottom: .5px solid var(--line); }

footer.page { max-width: 760px; margin: 64px auto 0; padding: 22px 24px 40px; border-top: .5px solid var(--line);
  color: var(--faint); font-size: 12.5px; display: flex; flex-wrap: wrap; gap: 4px 18px; }
footer.page .mono { color: var(--faint); }

@media (max-width: 620px) {
  h1 { font-size: 25px; } .thesis { font-size: 18px; } .finding { font-size: 17px; }
  .wrap { padding: 0 18px 72px; } nav.top { padding: 18px 18px 14px; }
}

@media print {
  :root { --bg: #fff; --ink: #000; --muted: #333; --line: #bbb; --hair: #ccc; }
  body { font-size: 11pt; } nav.top, footer.page, .counter { display: none; }
  a { border: 0; color: #000; } .wrap { max-width: none; }
  h2 { break-after: avoid; } table { break-inside: auto; } tr { break-inside: avoid; }
}
""".strip()
