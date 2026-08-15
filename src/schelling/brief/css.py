"""The brief page's self-contained stylesheet (Session 56, D56; restyled Session 57, D57).

A sealed-dossier treatment: an archival paper ground (a chosen warm neutral, not a default cream),
a single signal-red accent reserved for reality and the closest forecast, and a monospace utility
voice for every label, date and figure — the vocabulary of a precise, publicly-verifiable record.
Held verbatim so the page inlines it (no external fetch, offline-clean) and renders identically in
light and dark. The chart's colours are CSS custom properties defined here for both schemes.

Theme-aware three ways: the bare ``:root`` is the full light palette; ``prefers-color-scheme: dark``
(guarded so an explicit light choice still wins) and ``:root[data-theme="dark"]`` redefine only the
tokens. Components are styled through tokens, never inside a media/[data-theme] block.
"""

from __future__ import annotations

BRIEF_CSS = """:root{
  --paper:#f3f1ea; --panel:#fbfaf5; --plate:#eae7de;
  --ink:#181611; --ink-2:#565249; --ink-3:#8d897e;
  --rule:rgba(24,20,12,.11); --rule-2:rgba(24,20,12,.20); --rule-3:rgba(24,20,12,.06);
  --real:#a4361a; --real-tint:rgba(164,54,26,.07); --graphite:#5c6169;
  --shadow:0 1px 2px rgba(24,20,12,.05),0 8px 30px rgba(24,20,12,.05);
  --serif:Georgia,"Iowan Old Style",ui-serif,serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#100f0c; --panel:#191713; --plate:#0b0a08;
  --ink:#efece4; --ink-2:#a8a49a; --ink-3:#767268;
  --rule:rgba(255,255,255,.10); --rule-2:rgba(255,255,255,.22); --rule-3:rgba(255,255,255,.05);
  --real:#e2704f; --real-tint:rgba(226,112,79,.11); --graphite:#9aa1ab;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 12px 40px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --paper:#100f0c; --panel:#191713; --plate:#0b0a08;
  --ink:#efece4; --ink-2:#a8a49a; --ink-3:#767268;
  --rule:rgba(255,255,255,.10); --rule-2:rgba(255,255,255,.22); --rule-3:rgba(255,255,255,.05);
  --real:#e2704f; --real-tint:rgba(226,112,79,.11); --graphite:#9aa1ab;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 12px 40px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.65;font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit}
a:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--real);outline-offset:3px;
  border-radius:2px}

/* ---- masthead ---- */
.masthead{max-width:1180px;margin:0 auto;padding:18px clamp(20px,5vw,72px) 0;
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  font-family:var(--mono);font-size:11px;letter-spacing:.18em;color:var(--ink-3);
  text-transform:uppercase}
.masthead .mk{color:var(--ink);font-weight:600;letter-spacing:.34em}
.masthead .rt{display:flex;align-items:center;gap:14px;min-width:0}
.masthead .rt span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tag{border:1px solid var(--rule-2);border-radius:999px;padding:4px 11px;letter-spacing:.14em;
  color:var(--ink-2)}
.tag.sig{border-color:var(--real);color:var(--real)}
.rule-full{max-width:1180px;margin:14px auto 0;padding:0 clamp(20px,5vw,72px)}
.rule-full hr{border:0;border-top:1px solid var(--rule-2);margin:0}

.wrap{max-width:1180px;margin:0 auto;padding:clamp(30px,5vw,60px) clamp(20px,5vw,72px)
  clamp(28px,5vw,72px)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  color:var(--ink-3);margin:0 0 20px;text-transform:uppercase}
.eyebrow b{color:var(--real);font-weight:600}

/* ---- hero ---- */
.hero{display:grid;grid-template-columns:minmax(0,1fr);gap:clamp(22px,3vw,46px);align-items:end}
@media(min-width:860px){.hero{grid-template-columns:minmax(0,1.55fr) minmax(240px,.85fr)}}
h1{font-family:var(--serif);font-weight:400;font-size:clamp(30px,4.6vw,54px);
  line-height:1.12;letter-spacing:-.021em;margin:0;max-width:20ch;text-wrap:balance}
.stand{font-size:clamp(15px,1.25vw,18px);color:var(--ink-2);margin:20px 0 0;max-width:60ch}
.record{border:1px solid var(--rule);background:var(--panel);border-radius:14px;
  box-shadow:var(--shadow);overflow:hidden}
.record .rh{font-family:var(--mono);font-size:10px;letter-spacing:.18em;color:var(--ink-3);
  text-transform:uppercase;padding:12px 18px;border-bottom:1px solid var(--rule);
  background:var(--plate)}
.record dl{margin:0;padding:6px 18px 14px}
.record .row{display:flex;justify-content:space-between;align-items:baseline;gap:14px;
  padding:9px 0;border-bottom:1px solid var(--rule-3)}
.record .row:last-child{border-bottom:0}
.record dt{font-family:var(--mono);font-size:10.5px;letter-spacing:.13em;color:var(--ink-3);
  text-transform:uppercase}
.record dd{margin:0;font-family:var(--mono);font-size:14px;color:var(--ink);text-align:right}
.record dd.big{font-family:var(--serif);font-size:22px;color:var(--real);line-height:1}

/* ---- timeline ---- */
.beats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  margin:46px 0 0;border-top:1px solid var(--rule-2)}
.beat{position:relative;padding:26px 26px 22px 0;border-top:2px solid transparent;margin-top:-1px}
.beat::before{content:"";position:absolute;top:-6px;left:0;width:10px;height:10px;border-radius:50%;
  background:var(--paper);border:2px solid var(--graphite)}
.beat.sig::before{border-color:var(--real);background:var(--real)}
.beat+.beat{padding-left:26px}
@media(min-width:720px){.beat+.beat{border-left:1px solid var(--rule)}}
.beat .d{font-family:var(--mono);font-size:11px;letter-spacing:.12em;color:var(--real)}
.beat .t{font-family:var(--serif);font-size:20px;margin:7px 0 5px;letter-spacing:-.01em}
.beat .s{font-size:13.5px;color:var(--ink-2);line-height:1.55;max-width:34ch}

/* ---- section heads ---- */
.sec{margin-top:clamp(48px,6vw,68px)}
.sec-ey{font-family:var(--mono);font-size:11px;letter-spacing:.16em;color:var(--ink-3);
  text-transform:uppercase;display:flex;align-items:center;gap:12px;margin:0 0 10px}
.sec-ey::before{content:"";width:22px;height:1px;background:var(--real)}
h2{font-family:var(--serif);font-weight:400;font-size:clamp(21px,2.1vw,28px);
  letter-spacing:-.012em;margin:0 0 5px;text-wrap:balance}
.note{font-size:14px;color:var(--ink-3);margin:0 0 22px;max-width:66ch}

/* ---- figure panel ---- */
figure{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:16px;
  box-shadow:var(--shadow);overflow:hidden}
.panel-hd{display:flex;justify-content:space-between;align-items:center;gap:10px;
  padding:13px 20px;border-bottom:1px solid var(--rule);background:var(--plate);
  font-family:var(--mono);font-size:10.5px;letter-spacing:.15em;color:var(--ink-3);
  text-transform:uppercase}
figure svg{display:block;width:100%;padding:clamp(14px,2.2vw,26px)}
figcaption{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);letter-spacing:.05em;
  line-height:1.6;padding:12px 20px;border-top:1px solid var(--rule);background:var(--plate)}

/* ---- scores table ---- */
.table-wrap{overflow-x:auto;margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:15px;min-width:520px}
th{font-family:var(--mono);font-size:10px;letter-spacing:.13em;color:var(--ink-3);
  text-transform:uppercase;text-align:right;font-weight:400;
  padding:0 14px 11px 0;border-bottom:1px solid var(--rule-2)}
th:first-child,td:first-child{text-align:left;padding-left:14px}
th:last-child,td:last-child{padding-right:14px}
td{padding:13px 14px 13px 0;border-bottom:1px solid var(--rule);text-align:right;color:var(--ink-2)}
td.num{font-family:var(--mono);font-size:14px;color:var(--ink)}
tr.best td{color:var(--real);background:var(--real-tint)}
tr.best td:first-child{box-shadow:inset 3px 0 0 var(--real);font-weight:600}
tr.best td.num{color:var(--real)}
.vint{font-family:var(--mono);font-size:11px;color:var(--ink-3);letter-spacing:.05em}

/* ---- commentary + caveats ---- */
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
  gap:clamp(22px,3.4vw,50px);margin-top:12px}
p.pull{font-family:var(--serif);font-size:clamp(19px,1.85vw,24px);line-height:1.42;
  color:var(--ink);margin:0 0 16px;max-width:26ch;letter-spacing:-.01em}
p.body{color:var(--ink-2);margin:0 0 14px;max-width:60ch}
.caveats{list-style:none;margin:0;padding:0}
.caveats li{position:relative;color:var(--ink-2);margin-bottom:15px;padding-left:22px;
  max-width:58ch}
.caveats li::before{content:"";position:absolute;left:0;top:10px;width:9px;height:1px;
  background:var(--real)}
.caveats li:last-child{margin-bottom:0}

/* ---- verification plate ---- */
.verify{margin-top:clamp(48px,6vw,66px);border:1px solid var(--rule);border-radius:16px;
  overflow:hidden;background:var(--panel)}
.verify .vh{padding:18px 22px;border-bottom:1px solid var(--rule);background:var(--plate)}
.verify .seal{font-family:var(--mono);font-size:11px;letter-spacing:.06em;color:var(--ink-2);
  line-height:1.7;text-transform:uppercase}
.verify .seal b{color:var(--real);font-weight:600}
.verify .vb{padding:16px 22px;font-family:var(--mono);font-size:11px;letter-spacing:.03em;
  color:var(--ink-3);line-height:2}
.verify a{color:var(--ink-2);text-decoration:none;border-bottom:1px solid var(--rule-2)}
.verify a:hover{color:var(--real);border-color:var(--real)}
.verify .k{color:var(--ink-3)}

@media print{
  body{background:#fff;color:#000}
  .masthead,.record,figure,.verify{box-shadow:none}
  figure,.beat,.verify{break-inside:avoid}
}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}"""
