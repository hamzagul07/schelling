"""Published DEU model-comparison error rates, for context in the backtest write-up.

These are error rates reported in the literature for models predicting DEU/EU outcomes on the same
0-100 policy scale. They are cited for context only — they are NOT our numbers and are not directly
comparable (different DEU version, issue subset, capability/"clout" and resolve-variable handling).
The most relevant comparison is Bueno de Mesquita's own "Old Model" (the expected-utility /
challenge model our solver reconstructs), which his tests show losing to the simple weighted mean —
exactly the pattern our full-set backtest reproduces.
"""

from __future__ import annotations

from typing import NamedTuple


class PublishedResult(NamedTuple):
    model: str
    mean_abs_error: float
    subset: str
    source: str


# From Bueno de Mesquita (2011), Conflict Management and Peace Science 28(1), Tables 1 and 3.
# "Old Model" = the expected-utility/challenge model our engine is a reconstruction of; "MEAN /
# MEDIAN ROUND 1" = the input-data weighted mean / median with no strategic interplay.
PUBLISHED_RESULTS: tuple[PublishedResult, ...] = (
    PublishedResult(
        "Old Model (expected-utility / challenge)",
        21.5,
        "9 issues w/ resolve data",
        "BdM 2011, Table 1",
    ),
    PublishedResult(
        "Weighted mean, round 1", 11.8, "9 issues w/ resolve data", "BdM 2011, Table 1"
    ),
    PublishedResult(
        "Weighted median, round 1", 29.4, "9 issues w/ resolve data", "BdM 2011, Table 1"
    ),
    PublishedResult(
        "Old Model (expected-utility / challenge)",
        28.2,
        "issues w/o recursion point",
        "BdM 2011, Table 3",
    ),
    PublishedResult(
        "Weighted mean, round 1", 19.4, "issues w/o recursion point", "BdM 2011, Table 3"
    ),
    PublishedResult(
        "Weighted median, round 1", 19.8, "issues w/o recursion point", "BdM 2011, Table 3"
    ),
)

CITATIONS: tuple[str, ...] = (
    "Bueno de Mesquita, B. (2011). A New Model for Predicting Policy Choices: Preliminary Tests. "
    "Conflict Management and Peace Science 28(1): 1-21. doi:10.1177/0738894210388127.",
    "Achen, C. H. (2006). Institutional realism and bargaining models. In Thomson, Stokman, Achen "
    "& Konig (eds.), The European Union Decides. Cambridge University Press. (Finds the "
    "influence- and-salience-weighted mean of member positions did as well or better than more "
    "complex models.)",
    "Arregui, J. & Perarnaud, C. (2021). A new dataset on legislative decision-making in the "
    "European Union: the DEU III dataset. Journal of European Public Policy. doi:10.34810/data53.",
)

# The one-paragraph honest framing shared by the HTML report and BACKTEST.md.
CONTEXT_PROSE = (
    "The most-cited finding in this literature (Achen 2006, in Thomson et al.'s DEU project) is "
    "that the influence- and salience-weighted mean of member-state positions predicts EU "
    "outcomes as well as or better than the more complex bargaining and procedural models. Bueno "
    "de Mesquita's own tests on Thomson's data (2011) reproduce this: his 'Old Model' — the "
    "expected-utility / challenge model our solver reconstructs — records a mean absolute error "
    "around 21-28 on the 0-100 scale, losing to the simple weighted mean (~12-19). Our "
    "full-set result sits in the same regime and shows the same ordering."
)
