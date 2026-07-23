# GRADING — Q-2026-OPEC-SEP

**Pre-registered 2026-07-24, before resolution (2026-08-05); final after 2026-08-05.** Fixed in
advance so the score cannot be reverse-fit to the outcome. Referenced from
[FORECASTS.md](FORECASTS.md); its rationale is on the record in
[docs/questions/question-opec-sep.md](docs/questions/question-opec-sep.md).

**Binary criterion.** The question resolves on the collective production adjustment for September
2026 announced by the participating countries on or before 2026-08-05 23:59 UTC, as stated in the
OPEC Secretariat's published statement. If no adjustment is announced by that time, August levels
stand and the outcome is a rollover. If the statement announces a schedule rather than a single
figure, the September component governs. The headline collective adjustment figure governs, not
any compensation-adjusted figure quoted separately by third parties.

**Adjudicating sources (precedence order).** 1. The OPEC Secretariat's published statement and the
required-production table issued with it. 2. OPEC's Monthly Oil Market Report. 3. Wire services of
record (Reuters, Associated Press, Bloomberg) corroborating 1-2. Where sources genuinely conflict,
grade at the midpoint of the defensible range and record the disagreement.

**Mapping rule.** The announced collective adjustment in thousands of b/d maps linearly onto the
continuum:

    grade = 50 + (adjustment_kbd / 600) x 50

clamped to [0, 100] and rounded to the nearest integer. A cut is negative, an increase positive, a
rollover is exactly 50. The arithmetic governs; no discretionary band applies. The grader publishes
the announced figure, the computed grade, and the citation.

**Canonical text.** The sealed game's continuum text governs; the anchors above summarise it.

**Grading formula.** score(r) = |r.ensemble.median - actual| per sealed record on the 0-100
continuum. All sealed records are scored — challenge, compromise, and llm-judgment — and the grade,
its justification, and all cited sources are published in FORECASTS.md at grading.

**Integrity checks before scoring.** `schelling verify` on every sealed record; the ledger's
OpenTimestamps proof checked with `ots verify` to confirm the commitment predates resolution.

**Final:** no edits to this rubric under any circumstances after 2026-08-05.

<!-- Machine-readable rubric (D22.2 / D37): an ARITHMETIC mapping — no bands, so the report renders
the continuous density strip rather than band segments, and `schelling seal` accepts the question.
The prose above is canonical; this block is a faithful structuring of it. -->

```json
{
  "resolution_criteria": "The question resolves on the collective production adjustment for September 2026 announced by the participating OPEC+ countries in the additional voluntary adjustments on or before 2026-08-05 23:59 UTC, as stated in the OPEC Secretariat's published statement. If no adjustment is announced by that time, August levels stand and the outcome is a rollover. If the statement announces a schedule rather than a single figure, the September component governs. The headline collective adjustment figure governs, not any compensation-adjusted figure quoted separately by third parties.",
  "adjudicating_sources": [
    "The OPEC Secretariat's published statement and the required-production table issued with it",
    "OPEC's Monthly Oil Market Report",
    "Wire services of record (Reuters, Associated Press, Bloomberg) corroborating the above"
  ],
  "outcome_mapping": "Arithmetic mapping, no bands. The announced collective adjustment in thousands of b/d maps linearly onto the continuum: grade = 50 + (adjustment_kbd / 600) * 50, clamped to [0, 100] and rounded to the nearest integer. A cut is negative, an increase positive, a rollover is exactly 50. The arithmetic governs; no discretionary band applies. The grader publishes the announced figure, the computed grade, and the citation.",
  "grading_formula": "score(r) = |r.ensemble.median - actual| per sealed record on the 0-100 continuum. All sealed records are scored (challenge, compromise, llm-judgment); the grade, its justification, and all cited sources are published in FORECASTS.md at grading."
}
```
