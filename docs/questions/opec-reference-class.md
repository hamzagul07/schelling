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

<!-- Part B (the sourced enumeration, coverage, mapped distribution, and COMPLETE/INCOMPLETE verdict)
is appended below only AFTER this definition is committed. -->
