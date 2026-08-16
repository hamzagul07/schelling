# Reference class — OPEC+ additional-voluntary-adjustment monthly decisions

The sessions-at-risk denominator (D30.1/D30.2) for the OPEC monthly-decision series
(`Q-2026-OPEC-SEP`, `Q-2026-OPEC-OCT`, and the months that follow). Built **denominator-first**:
the population is fixed by construction before any outcome is sourced, so the class cannot be shaped
by what happens to be easy to find (D30.1: "enumerate the denominator before you count the
numerator"). Ratification is required before this feeds any forecast.

---

## Part A — Pre-registered definition (written 2026-08-16, BEFORE any outcome was sourced)

*This section is committed on its own, before sourcing begins, so the inclusion rules are fixed in
advance and cannot be reverse-fit to the data.*

### The decision type (the unit)

One **production month's collective crude-production adjustment** by the OPEC+ producers
implementing the *additional voluntary adjustments* (AVAs) — the net change, in thousand b/d, of the
group's collective required production for that month relative to the previous month. This is
exactly the quantity `Q-2026-OPEC-OCT` forecasts for October 2026. A cut is negative, an increase
positive, and a month in which the group holds its level unchanged is a **rollover of 0**.

### The denominator, fixed by construction

One unit per production month, from the start of the AVA regime through the most recent month
resolved before the forecast month:

- **Start.** The additional voluntary adjustments began with the 1.65 mb/d tranche, decided at the
  OPEC+ meeting of 2–3 April 2023 and effective **May 2023**. May 2023 is therefore the first
  in-scope production month.
- **End.** The most recent *resolved* decision as of drafting is the 2 August 2026 meeting, which
  set **September 2026** (the graded `Q-2026-OPEC-SEP` outcome). September 2026 is the last in-scope
  month; **October 2026 is excluded — it is the question, the numerator, not the denominator.**
- **Count.** May 2023 → September 2026 inclusive = **N = 41 months** (2023: 8, 2024: 12, 2025: 12,
  2026: 9). This count is known by reading the calendar, without discovering a single outcome.

### How the edge cases are treated (stated in advance)

- **The two tranches (1.65 mb/d and 2.2 mb/d).** The unit is the *month-over-month collective
  change*, so both tranches are handled by one consistent rule and need no special-casing: a
  tranche's establishment appears as the collective cut at its **effective month** (a large negative
  change, which the continuum clamps to its low pole), and every later month in which the programme
  merely continued unchanged is a **rollover of 0**. The 1.65 mb/d tranche took effect May 2023; the
  2.2 mb/d tranche (the group whose monthly decisions this series forecasts) took effect January
  2024.
- **The eight-to-seven membership change.** The UAE left OPEC/OPEC+ effective 1 May 2026, taking the
  AVA group from eight participants to seven. The outcome variable is the group's *announced headline
  collective figure as constituted that month*; a change in membership changes who is in the group
  but not the definition of the monthly collective-adjustment outcome, so the series stays
  comparable across the change. (Where a month's headline figure is quoted only for the
  post-departure seven, that is the figure of record for that month.)
- **A month with no announcement.** Counts as a **rollover of 0** — a real outcome (the group met or
  was scheduled to and left the level unchanged), never a missing cell. Actively sourcing these
  holds is required (D30.2); a pause is a data point, not a gap.

### The mapping and the completeness rule

- Each month's sourced figure is mapped through **the question's committed `outcome_map`**
  (`GRADING-Q-2026-OPEC-OCT.md`: `grade = 20 + (adjustment_kbd / 750) × 100`, clamped to [0, 100],
  two decimals) to place it on the new continuum. The base rate is the distribution of those mapped
  values.
- **D30.2 completeness rule.** A base rate is claimed **only if the class is COMPLETE** — every one
  of the N months has a sourced outcome (coverage M/N = 1). If coverage is partial, the distribution
  is reported over what is sourced and **labelled INCOMPLETE**; no base rate is asserted from a
  partial class. "INCOMPLETE beats a biased base rate."
- **Ratification.** Nothing here feeds a forecast until a human ratifies both the enumeration and its
  completeness verdict. Until then it is candidate evidence only.

---

## Part B — Sourced enumeration and completeness (sourced 2026-08-16, after Part A was committed)

Sourcing followed the pre-registered definition. opec.org is bot-blocked to the archive fetcher but
its `pr-detail` statements are reachable one-by-one; those are the primary source, corroborated by
reachable mirrors (CNBC, World Oil, Euronews, The Tribune, GlobalSecurity carrying Saudi Press
Agency, Aegis "OPEC Watch"). Pauses were searched for actively, not just increases.

### The enumeration (each month's collective adjustment, mapped through the OCT `outcome_map`)

`continuum = 20 + (kb/d ÷ 750) × 100`, clamped [0, 100], two decimals — computed, not typed.

| Month | Adjustment (kb/d) | Continuum | Source / note |
|---|---:|---:|---|
| 2023-05 | −1660 | 0.00 | 1.65 mb/d tranche established (eff. May 2023) — Aegis/Reuters. Clamped. |
| 2023-06 | 0 | 20.00 | hold — Aegis |
| 2023-07 | −1000 | 0.00 | Saudi extra 1 mb/d voluntary cut — Aegis. Clamped. |
| 2023-08 | 0 | 20.00 | Saudi cut extended (hold) — Aegis |
| 2023-09 | 0 | 20.00 | extended (hold) — Aegis |
| 2023-10 | 0 | 20.00 | extended thru Dec (hold) — Aegis |
| 2023-11 | 0 | 20.00 | hold — Aegis |
| 2023-12 | 0 | 20.00 | hold — Aegis |
| 2024-01 | −2200 | 0.00 | 2.2 mb/d tranche established (eff. Jan 2024) — Aegis/Reuters. Clamped. |
| 2024-02 … 2025-03 | — | — | **14 months not individually sourced** (2.2 held, unwind repeatedly delayed to Apr 2025) — block context only |
| 2025-04 | +138 | 38.40 | unwind begins — GlobalSecurity/SPA, Reuters |
| 2025-05 | +411 | 74.80 | +411 (triple step) — Reuters |
| 2025-06 | +411 | 74.80 | +411 — Reuters |
| 2025-07 | +411 | 74.80 | +411 — The Tribune |
| 2025-08 | +548 | 93.07 | +548 — CNBC (5 Jul 2025) |
| 2025-09 | +547 | 92.93 | +547 — **opec.org pr-detail/572** (3 Aug 2025) |
| 2025-10 | +137 | 38.27 | 1.65 unwind begins — GlobalSecurity/SPA (7 Sep 2025) |
| 2025-11 | +137 | 38.27 | +137 — Reuters/SPA |
| 2025-12 | +137 | 38.27 | +137 — Reuters (2 Nov 2025) |
| 2026-01 | 0 | 20.00 | Q1 pause — Reuters ("paused during Q1 2026") |
| 2026-02 | 0 | 20.00 | pause (seasonality) — **opec.org pr-detail/587** (4 Jan 2026) |
| 2026-03 | 0 | 20.00 | pause — **opec.org pr-detail/589** (1 Feb 2026) |
| 2026-04 | +206 | 47.47 | resume, 1.65 unwind — Reuters/Substack |
| 2026-05 | +206 | 47.47 | +206 — Reuters |
| 2026-06 | +188 | 45.07 | +188, first meeting without the UAE — CNBC (3 May 2026) |
| 2026-07 | +188 | 45.07 | +188 — **opec.org pr-detail/604** (7 Jun 2026) |
| 2026-08 | +188 | 45.07 | +188 (7 countries) — World Oil (5 Jul 2026) |
| 2026-09 | +188 | 45.07 | +188 — graded `Q-2026-OPEC-SEP` outcome (FORECASTS.md; OPEC statement 2 Aug 2026) |

### Coverage and completeness verdict

- **N (denominator, fixed by construction)** = 41 production months (May 2023 → Sep 2026).
- **M (months with a sourced outcome)** = 27.
- **Coverage M/N = 27/41 = 65.9%.** The 14 uncovered months (Feb 2024 → Mar 2025) are the delayed-
  unwind holds; block context places them at rollover, but no month-specific statement was sourced
  for them, so they are **not counted** as sourced.
- **Verdict: INCOMPLETE.** Per the D30.2 rule, **no base rate is claimed from a partial class.** The
  distribution below is over the 27 sourced months only and is **labelled incomplete**; it is a
  description of what was sourced, not a base rate.

### Distribution over the 27 SOURCED months (incomplete — not a base rate)

| Continuum region | Months |
|---|---:|
| 0.00 (cut ≥150 kb/d, clamped) | 3 |
| 20.00 (rollover / pause) | 9 |
| (20, 40) small increase | 4 |
| [40, 60) increase ≈150–300 kb/d | 6 |
| [60, 80) increase ≈300–450 kb/d | 3 |
| [80, 100] increase ≥≈450 kb/d | 2 |

Sourced continuum: min 0.00 · median 38.27 · max 93.07. Descriptively (and only descriptively,
because the class is incomplete): the sourced months are dominated by holds/pauses (rollover 20) and
by increases; the recent 2026 cadence sits at ≈45 (a +188 kb/d increase), with April–May 2026 at
≈47 (+206). If the 14 inferred holds were ratified as rollovers, the class would complete and skew
further toward rollover — but that is a ratification decision, not an assumption made here.

### Ratification

**Status: NOT RATIFIED.** This enumeration and its INCOMPLETE verdict are candidate evidence only.
Nothing here feeds a forecast, a formalization, or a solve until a human ratifies (a) the pre-
registered definition, (b) the sourced outcomes, and (c) either the INCOMPLETE verdict or a decision
to ratify the 14 inferred holds as rollovers (which would make the class COMPLETE). Logged D57.2.
