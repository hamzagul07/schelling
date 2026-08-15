"""The brief page's self-contained stylesheet — Hassan's approved ``first-graded-forecast.html``
design (Session 56, D56). Held verbatim as a constant so the page inlines it (no external fetch)
and every brief renders identically offline, in light and dark. The chart's colours are CSS custom
properties defined here for both schemes, so a generated SVG stays legible either way."""

from __future__ import annotations

BRIEF_CSS = """:root{
  --paper:#f7f5f0; --card:#fffdf9; --ink:#14140f; --ink-2:#57564d;
  --ink-3:#8e8c81; --rule:rgba(0,0,0,.10); --rule-2:rgba(0,0,0,.22);
  --real:#a4361a; --graphite:#5c6169;
  --serif:Georgia,"Iowan Old Style",ui-serif,serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#111110; --card:#191917; --ink:#eeece5; --ink-2:#a7a59b;
  --ink-3:#75736a; --rule:rgba(255,255,255,.11); --rule-2:rgba(255,255,255,.24);
  --real:#e2704f; --graphite:#9aa1ab;}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.65;font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:clamp(28px,5vw,72px)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  color:var(--ink-3);margin:0 0 22px;text-transform:uppercase}
h1{font-family:var(--serif);font-weight:400;font-size:clamp(28px,4.4vw,52px);
  line-height:1.14;letter-spacing:-.02em;margin:0;max-width:22ch}
.stand{font-size:clamp(15px,1.3vw,18px);color:var(--ink-2);margin:20px 0 0;max-width:68ch}

.beats{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:1px;background:var(--rule);border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule);margin:44px 0 0}
.beat{background:var(--paper);padding:20px 22px}
.beat .d{font-family:var(--mono);font-size:11px;letter-spacing:.1em;color:var(--real)}
.beat .t{font-family:var(--serif);font-size:19px;margin:6px 0 4px}
.beat .s{font-size:13.5px;color:var(--ink-2);line-height:1.5}

h2{font-family:var(--serif);font-weight:400;font-size:clamp(20px,2vw,26px);
  letter-spacing:-.01em;margin:56px 0 4px}
.note{font-size:14px;color:var(--ink-3);margin:0 0 22px}

figure{margin:0;background:var(--card);border:1px solid var(--rule);
  border-radius:14px;padding:clamp(16px,2.4vw,30px)}
figcaption{font-family:var(--mono);font-size:11px;color:var(--ink-3);
  letter-spacing:.05em;margin-top:16px;line-height:1.6}

table{width:100%;border-collapse:collapse;margin-top:6px;font-size:15px}
th{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--ink-3);
  text-transform:uppercase;text-align:right;font-weight:400;
  padding:0 0 10px;border-bottom:1px solid var(--rule-2)}
th:first-child,td:first-child{text-align:left}
td{padding:11px 0;border-bottom:1px solid var(--rule);text-align:right}
td.num{font-family:var(--mono);font-size:14px}
tr.best td{color:var(--real)}
.vint{font-family:var(--mono);font-size:11px;color:var(--ink-3);letter-spacing:.06em}

.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));
  gap:clamp(20px,3vw,44px);margin-top:10px}
p.body{color:var(--ink-2);margin:0 0 14px;max-width:64ch}
.pull{font-family:var(--serif);font-size:clamp(18px,1.8vw,23px);line-height:1.45;
  color:var(--ink);margin:0 0 14px;max-width:30ch}

.caveats{border-left:2px solid var(--real);padding-left:22px;margin-top:14px}
.caveats li{color:var(--ink-2);margin-bottom:12px;max-width:62ch}
.caveats li:last-child{margin-bottom:0}

footer{margin-top:60px;border-top:1px solid var(--rule);padding-top:22px;
  font-family:var(--mono);font-size:11.5px;color:var(--ink-3);line-height:1.9;
  letter-spacing:.03em}
footer a{color:var(--ink-2)}
@media print{body{background:#fff}figure{break-inside:avoid}}"""
