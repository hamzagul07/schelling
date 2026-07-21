"""Sourced capability table for DEU actors (Session 10, D10.1-D10.3).

DEU records no capability. The published DEU convention is the Shapley-Shubik power index
(Arregui, Stokman & Thomson 2004, *European Union Politics*, p. 592); here we use the transparent,
fully-citable approximation Hassan approved: each member state's capability is its Council power in
the treaty regime in force at the issue's decision date (D10.2) —

* **pre-Nice (to 31 Oct 2004)** — weighted Council votes under the pre-Nice EC weighting
  (Germany/France/Italy/UK = 10 ... Luxembourg = 2; total 87, QM 62). Source: Treaty establishing
  the EC, art. 148 (Amsterdam consolidation).
* **Nice (1 Nov 2004 - 31 Oct 2014)** — weighted Council votes under the Treaty of Nice
  (Germany/France/Italy/UK = 29 ... Malta = 3; EU-27 total 345, QM 255; Croatia = 7 from 2013).
  Source: Treaty of Nice, OJ C 80 (2001), Declaration on enlargement.
* **Lisbon (from 1 Nov 2014)** — QMV is a population-based double majority with NO vote weights, so
  the capability proxy is each state's population (millions, ~2019). Source: Eurostat via Wikipedia
  "Member state of the European Union" (retrieved 2026-07-21).

The Commission and European Parliament have no Council vote; per Hassan's decision they each
receive the **largest member-state capability** in that regime (D10.3), i.e. 100 after
normalization. Every regime's raw values are rescaled so the strongest actor = 100 (the Policon
procedure). The same table feeds the solver AND the weighted-mean baseline — equal treatment.
"""

from __future__ import annotations

# --- pre-Nice EC Council weights (to 31 Oct 2004); total 87 ---------------------------------------
PRE_NICE_WEIGHTS: dict[str, float] = {
    "de": 10,
    "fr": 10,
    "it": 10,
    "uk": 10,
    "es": 8,
    "be": 5,
    "el": 5,
    "nl": 5,
    "pt": 5,
    "at": 4,
    "se": 4,
    "dk": 3,
    "ie": 3,
    "fi": 3,
    "lu": 2,
}

# --- Treaty of Nice Council weights (1 Nov 2004 - 31 Oct 2014); EU-27 total 345, +Croatia 7 -------
NICE_WEIGHTS: dict[str, float] = {
    "de": 29,
    "fr": 29,
    "it": 29,
    "uk": 29,
    "es": 27,
    "pl": 27,
    "ro": 14,
    "nl": 13,
    "be": 12,
    "cz": 12,
    "el": 12,
    "hu": 12,
    "pt": 12,
    "at": 10,
    "bu": 10,
    "se": 10,
    "dk": 7,
    "ie": 7,
    "lt": 7,
    "sk": 7,
    "fi": 7,
    "cr": 7,
    "ee": 4,
    "lv": 4,
    "si": 4,
    "cy": 4,
    "lu": 4,
    "mt": 3,
}

# --- Lisbon-era populations in millions (~2019); population IS the QMV weight under double majority
LISBON_POPULATION: dict[str, float] = {
    "de": 83.12,
    "fr": 67.44,
    "uk": 67.79,
    "it": 58.97,
    "es": 48.95,
    "pl": 37.84,
    "ro": 19.19,
    "nl": 17.61,
    "be": 11.57,
    "el": 10.38,
    "cz": 10.57,
    "pt": 10.75,
    "se": 10.37,
    "hu": 9.73,
    "at": 8.93,
    "bu": 6.92,
    "dk": 5.83,
    "fi": 5.53,
    "sk": 5.42,
    "ie": 5.01,
    "cr": 4.04,
    "lt": 2.80,
    "si": 2.11,
    "lv": 1.86,
    "ee": 1.33,
    "cy": 0.90,
    "lu": 0.63,
    "mt": 0.52,
}

_INSTITUTIONS = ("com", "ep")

# Self-checks pinning the sourced totals (documents the source; fails loudly on a typo).
assert sum(PRE_NICE_WEIGHTS.values()) == 87, "pre-Nice Council weights must total 87"
assert sum(NICE_WEIGHTS[c] for c in NICE_WEIGHTS if c != "cr") == 345, "Nice EU-27 must total 345"


def regime_for_year(year: int) -> str:
    """Which treaty voting regime was in force in a given decision year (D10.2).

    Cutoffs land in the empty gaps of the DEU decision-date distribution (no issues 2002-2004 or
    2010-2015), so the mapping is unambiguous: <=2004 pre-Nice, 2005-2014 Nice, >=2015 Lisbon.
    """
    if year <= 2004:
        return "pre_nice"
    if year <= 2014:
        return "nice"
    return "lisbon"


def _regime_table(regime: str) -> dict[str, float]:
    return {
        "pre_nice": PRE_NICE_WEIGHTS,
        "nice": NICE_WEIGHTS,
        "lisbon": LISBON_POPULATION,
    }[regime]


def capabilities_for_issue(codes: list[str], year: int) -> dict[str, float]:
    """Capability (0-100) for each actor code present on an issue decided in ``year``.

    Member states take their regime power; the Commission/EP each take the largest member-state
    power (D10.3). All values are rescaled so the strongest actor = 100. A member-state code with
    no regime entry (should not occur given the period clusters) falls back to the regime minimum.
    """
    table = _regime_table(regime_for_year(year))
    states = [c for c in codes if c not in _INSTITUTIONS]
    state_powers = [table[c] for c in states if c in table]
    max_state = max(state_powers) if state_powers else 1.0
    min_state = min(state_powers) if state_powers else 1.0

    raw: dict[str, float] = {}
    for c in codes:
        if c in _INSTITUTIONS:
            raw[c] = max_state  # largest-state weight (D10.3)
        else:
            raw[c] = table.get(c, min_state)

    scale = max(raw.values()) or 1.0
    return {c: raw[c] / scale * 100.0 for c in codes}
