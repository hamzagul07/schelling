# GRADING — Q-2026-OPEC-OCT

**Pre-registered 2026-08-16, before resolution (2026-09-10); final after 2026-09-10.** Fixed in
advance so the score cannot be reverse-fit to the outcome. Referenced from
[FORECASTS.md](FORECASTS.md); its rationale is on the record in
[docs/questions/question-opec-oct.md](docs/questions/question-opec-oct.md).

**Binary criterion.** The question resolves on the collective production adjustment for October
2026 announced by the OPEC+ countries participating in the additional voluntary adjustments, at or
following their meeting scheduled for 6 September 2026, on or before 2026-09-10 23:59 UTC, as stated
in the OPEC Secretariat's published statement. If no adjustment is announced by that time, September
levels stand and the outcome is a rollover. If the statement announces a schedule rather than a
single figure, the October component governs. The headline collective adjustment figure governs,
not any compensation-adjusted figure quoted separately by third parties.

**Adjudicating sources (precedence order).** 1. The OPEC Secretariat's published statement and the
required-production table issued with it. 2. OPEC's Monthly Oil Market Report. 3. Wire services of
record (Reuters, Associated Press, Bloomberg) corroborating 1-2. Where sources genuinely conflict,
grade at the midpoint of the defensible range and record the disagreement.

**Mapping rule.** The announced collective adjustment in thousands of b/d maps linearly onto the
continuum, anchored to the plausible range for this decision (a cut of 150 kb/d at one pole, an
increase of 600 kb/d at the other) so the status-quo rollover sits near a pole rather than the
midpoint (D28.0):

    grade = 20 + (adjustment_kbd / 750) x 100

clamped to [0, 100] and **rounded to two decimal places** (ties up). A cut is negative, an increase
positive; a rollover (no change) is exactly 20; a 150 kb/d cut is 0; a 600 kb/d increase is 100. The
arithmetic governs; no discretionary band applies. The grader publishes the announced figure, the
computed grade, and the citation.

**Canonical text.** The sealed game's continuum text governs; the anchors above summarise it.

**Grading formula.** score(r) = |r.ensemble.median - actual| per sealed record on the 0-100
continuum. All sealed records are scored — challenge, compromise, and llm-judgment — and the grade,
its justification, and all cited sources are published in FORECASTS.md at grading.

**Integrity checks before scoring.** `schelling verify` on every sealed record; the ledger's
OpenTimestamps proof checked with `ots verify` to confirm the commitment predates resolution.

**Final:** no edits to this rubric under any circumstances after 2026-09-10.

<!-- Machine-readable rubric (D22.2 / D37): an ARITHMETIC mapping — no bands, so the report renders
the continuous density strip rather than band segments, and `schelling seal` accepts the question.
The prose above is canonical; this block is a faithful structuring of it. -->

```json
{
  "resolution_criteria": "The question resolves on the collective production adjustment for October 2026 announced by the OPEC+ countries participating in the additional voluntary adjustments, at or following their meeting scheduled for 6 September 2026, on or before 2026-09-10 23:59 UTC, as stated in the OPEC Secretariat's published statement. If no adjustment is announced by that time, September levels stand and the outcome is a rollover. If the statement announces a schedule rather than a single figure, the October component governs. The headline collective adjustment figure governs, not any compensation-adjusted figure quoted separately by third parties.",
  "adjudicating_sources": [
    "The OPEC Secretariat's published statement and the required-production table issued with it",
    "OPEC's Monthly Oil Market Report",
    "Wire services of record (Reuters, Associated Press, Bloomberg) corroborating the above"
  ],
  "outcome_mapping": "Arithmetic mapping, no bands. The announced collective adjustment in thousands of b/d maps linearly onto the continuum, anchored to the plausible range (a 150 kb/d cut at 0, a 600 kb/d increase at 100): grade = 20 + (adjustment_kbd / 750) * 100, clamped to [0, 100] and rounded to two decimal places (ties up). A cut is negative, an increase positive; a rollover is exactly 20. The arithmetic governs; no discretionary band applies. The grader publishes the announced figure, the computed grade, and the citation.",
  "grading_formula": "score(r) = |r.ensemble.median - actual| per sealed record on the 0-100 continuum. All sealed records are scored (challenge, compromise, llm-judgment); the grade, its justification, and all cited sources are published in FORECASTS.md at grading.",
  "outcome_map": {
    "unit": "thousand b/d (announced collective October adjustment)",
    "slope": 0.13333333333333333,
    "intercept": 20.0,
    "clamp_lo": 0.0,
    "clamp_hi": 100.0,
    "rounding": "nearest_hundredth_half_up"
  }
}
```

**`outcome_map` provenance (added 2026-08-16, pre-resolution).** The `outcome_map` block above is a
machine-readable restatement of the mapping rule already committed in `outcome_mapping` and in the
"Mapping rule" prose: `grade = 20 + (adjustment_kbd / 750) × 100`, i.e. `intercept = 20` and
`slope = 100/750 = 0.13333…` continuum units per thousand b/d, clamped to `[0, 100]`. The anchors
are asymmetric by design — the plausible range for this decision runs from a modest cut to a large
increase, and D28.0 says never to site the status quo at the midpoint, so the rollover lands at 20.
The rounding, made explicit here as `nearest_hundredth_half_up` (D57.1), keeps **two decimals** — at
a slope of 0.133 per kbd, whole-integer grading would flatten ~7.5 kbd of real resolution into each
step, so this continuum grades to the hundredth (65.665 → 65.67, ties up). It carries **no semantic
change**: it exists only so `schelling grade` can compute the settlement without a human
transcribing the formula at grading time (D49.2). **The prose governs on any disagreement.** Like the
rest of the rubric the `outcome_map` is excluded from `inputs_hash`, so no sealed record, ledger
entry, or timestamp is affected; a drift-guard test (`test_opec_oct_outcome_map_matches_prose`) pins
the executable form to the prose formula and checks the two-decimal boundary, exactly as D24.4 did
for the band arrays and D49.2 did for the September map.
