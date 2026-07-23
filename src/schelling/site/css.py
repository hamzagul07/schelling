"""The one stylesheet (D31.4; restyled to the vast full-scale reference in D35). Self-contained:
system font stacks only — no external fonts, imports, or network. A sticky 260px left sidebar with a
numbered section index; a full-bleed content column with ``clamp()`` side padding that collapses to a
horizontal bar under 900px. Serif for the hero and section headings, sans for body, monospace for
identifiers/hashes/figures; one accent plus a teal support colour; tabular figures throughout; 1px
hairlines; no shadows or gradients; dark mode via ``prefers-color-scheme``. Section ordinals are CSS
counters, so no number is hand-typed. Adapted from Hassan's approved ``site-reference-vast.html``.
"""

SITE_CSS = """
:root{
  --bg:#faf9f6; --panel:#f2f0ea; --card:#fff;
  --ink:#16160f; --ink-2:#54534b; --ink-3:#8b8980;
  --line:rgba(0,0,0,.09); --line-2:rgba(0,0,0,.16);
  --accent:#a8480d; --teal:#0f6e56;
  --serif:ui-serif,Georgia,"Iowan Old Style",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f0f0d; --panel:#171714; --card:#1b1b18;
  --ink:#f0efe9; --ink-2:#a6a49b; --ink-3:#74726a;
  --line:rgba(255,255,255,.10); --line-2:rgba(255,255,255,.18);
  --accent:#e29a4e; --teal:#5dcaa5;}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
 font-size:16px;line-height:1.7;font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}

.shell{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}
aside{border-right:1px solid var(--line);padding:40px 28px;position:sticky;top:0;height:100vh;
 display:flex;flex-direction:column;gap:28px;background:var(--panel)}
.mark{font-family:var(--mono);font-size:12px;letter-spacing:.14em;color:var(--ink-2)}
.idx{display:flex;flex-direction:column;gap:2px;font-size:13px;counter-reset:idx}
.idx a{color:var(--ink-2);padding:5px 0;display:flex;gap:12px;counter-increment:idx}
.idx a:hover,.idx a[aria-current]{color:var(--accent)}
.idx .n{font-family:var(--mono);font-size:11px;color:var(--ink-3);width:18px}
.idx .n::before{content:counter(idx,decimal-leading-zero)}
.asidefoot{margin-top:auto;font-size:11px;color:var(--ink-3);font-family:var(--mono);line-height:1.8}

main{padding:0;counter-reset:sec}
.bleed{padding:0 clamp(28px,5vw,96px)}
.rule{border-top:1px solid var(--line);margin-top:0}
.sechead{display:flex;align-items:baseline;gap:16px;padding:18px 0 0}
.sechead .n{font-family:var(--mono);font-size:11px;color:var(--ink-3);letter-spacing:.1em}
.sechead .n::before{content:counter(sec,decimal-leading-zero)}
.sechead h2{font-family:var(--serif);font-weight:400;font-size:clamp(22px,2.2vw,30px);margin:0;
 letter-spacing:-.015em}
section{padding-bottom:clamp(56px,7vw,110px);counter-increment:sec}

.hero{padding-top:clamp(64px,9vw,140px);padding-bottom:clamp(40px,5vw,72px)}
.hero h1{font-family:var(--serif);font-weight:400;letter-spacing:-.025em;line-height:1.06;
 font-size:clamp(40px,7.2vw,104px);margin:22px 0 0;max-width:15ch}
.hero h1 .turn{display:block;color:var(--accent)}
.lede{font-size:clamp(16px,1.35vw,20px);color:var(--ink-2);line-height:1.65;margin:32px 0 0;
 max-width:64ch}
.cta{display:flex;gap:12px;flex-wrap:wrap;margin-top:36px}
.cta a{font-size:14px;padding:11px 20px;border:1px solid var(--line-2);border-radius:10px}
.cta a:hover{background:var(--panel)}
.cta a.p{border-color:var(--accent);color:var(--accent)}

.grid{display:grid;gap:1px;background:var(--line);border-top:1px solid var(--line);
 border-bottom:1px solid var(--line);grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.cell{background:var(--bg);padding:26px clamp(20px,2.4vw,34px)}
.cell .k{font-size:12px;color:var(--ink-3);margin:0 0 8px;font-family:var(--mono);letter-spacing:.06em}
.cell .v{font-family:var(--serif);font-size:clamp(30px,3.6vw,46px);line-height:1;margin:0;
 letter-spacing:-.02em}
.cell .s{font-size:12px;color:var(--ink-3);margin:8px 0 0}

.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
 gap:clamp(24px,3vw,56px);margin-top:28px}
p.body{color:var(--ink-2);max-width:68ch;margin:16px 0 0}
p.body a{color:var(--accent)}
.big{font-family:var(--serif);font-size:clamp(20px,2vw,27px);line-height:1.45;
 color:var(--ink);max-width:34ch;margin:0;letter-spacing:-.01em}
.deep{display:inline-block;margin-top:20px;font-family:var(--mono);font-size:13px;color:var(--accent)}
.deep:hover{text-decoration:underline}

figure{margin:32px 0 0}
figcaption{font-family:var(--mono);font-size:11px;color:var(--ink-3);margin-top:14px;
 letter-spacing:.04em;text-transform:uppercase}
.fig-title{font-family:var(--serif);font-size:15px;fill:var(--ink)}
.fig-legend{font-family:var(--sans);font-size:12px;fill:var(--ink-2)}
.fig-num{font-family:var(--mono);font-size:12px;fill:var(--ink-2)}
.fig-tick{font-family:var(--mono);font-size:11px;fill:var(--ink-3)}
.fig-modal-lab{font-family:var(--sans);font-size:11px;fill:var(--ink-2)}
.fig-verdict{font-family:var(--mono);font-size:12px;letter-spacing:.04em}
.fig-modal{fill:var(--panel)}
.fig-rule{stroke:var(--ink-3);opacity:.28}
.fig-axis{stroke:var(--ink-3);opacity:.42}

.rows{margin-top:26px;border-top:1px solid var(--line)}
.row{display:grid;grid-template-columns:minmax(0,2.4fr) 1fr .8fr 1fr;gap:20px;align-items:baseline;
 padding:16px 0;border-bottom:1px solid var(--line)}
.row .q{font-size:16px}
.row .q code{font-family:var(--mono);font-size:13px}
.row .m{font-size:13px;color:var(--ink-2)}
.row .v{font-family:var(--mono);font-size:14px;text-align:right}
.row .d{font-size:13px;color:var(--ink-2);text-align:right}
.row .g{font-size:15px}
.row .r{font-family:var(--mono);font-size:13px;color:var(--accent);text-align:right}
.row .h{grid-column:1/-1;font-family:var(--mono);font-size:11px;color:var(--ink-3);
 word-break:break-all;margin:-6px 0 0}

.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-top:26px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 24px}
.card .t{font-family:var(--mono);font-size:11px;color:var(--ink-3);letter-spacing:.08em;margin:0 0 10px}
.card h3{font-family:var(--serif);font-weight:400;font-size:19px;margin:0 0 8px}
.card p{font-size:14px;color:var(--ink-2);margin:0;line-height:1.65}
.card a{color:var(--accent);font-family:var(--mono);font-size:12px}

.biblist{list-style:none;margin:26px 0 0;padding:0;border-top:1px solid var(--line)}
.biblist li{font-size:14px;color:var(--ink-2);line-height:1.6;padding:12px 0 12px 24px;
 text-indent:-24px;border-bottom:1px solid var(--line);max-width:80ch}

pre{background:var(--panel);border-radius:12px;padding:20px 24px;overflow-x:auto;
 font-family:var(--mono);font-size:13px;line-height:1.75;color:var(--ink-2);margin:24px 0 0}
h3.sub{font-family:var(--sans);font-weight:500;font-size:14px;margin:24px 0 0}
footer{border-top:1px solid var(--line);padding:40px 0 80px;font-size:12px;
 color:var(--ink-3);font-family:var(--mono);letter-spacing:.04em}

@media(max-width:900px){
 .shell{grid-template-columns:1fr}
 aside{position:static;height:auto;flex-direction:row;flex-wrap:wrap;align-items:center;
  gap:16px;padding:18px 24px;border-right:0;border-bottom:1px solid var(--line)}
 .idx{flex-direction:row;flex-wrap:wrap;gap:14px}.idx .n{display:none}.asidefoot{display:none}
 .row{grid-template-columns:1fr 1fr;gap:8px}.row .d,.row .v,.row .r{text-align:left}
}
@media print{aside,.cta{display:none}.shell{display:block}body{background:#fff;color:#000}}
""".strip()
