"""The static site (Session 31, D31).

``schelling site build`` regenerates every page under ``docs/`` from the repository's own
artifacts — the sealed ledger (``FORECASTS.md``), the backtest leaderboard (``BACKTEST.md``), the
paper's evidence table (``paper/EVIDENCE.md``), the decisions log, the test count, and the HEAD
commit. No figure is ever hand-typed into the HTML; ``site build --check`` fails CI if the committed
site differs from a fresh regeneration. The pages are plain, self-contained HTML + one CSS file — no
framework, no build step, no external fonts or scripts — the same offline-clean rule as the reports.
"""

from schelling.site.data import SiteData, gather
from schelling.site.render import build_site, check_site, write_site

__all__ = ["SiteData", "build_site", "check_site", "gather", "write_site"]
