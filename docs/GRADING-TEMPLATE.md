# GRADING template — the pre-registered rubric a question is sealed with

Copy this file to `GRADING-<question_id>.md` at the repo root and fill every field **before**
sealing, so the score can never be reverse-fit to the outcome. The prose is canonical; the
machine-readable ```json``` block at the bottom is a faithful structuring of it and is what the
report and `schelling` tooling read.

Since **Session 40 (D40.1)** the rubric declares a **proper scoring rule as its primary metric** and
keeps **absolute error** (`|median - actual|`) as an explicit **secondary**. A proper scoring rule
reads the whole forecast distribution — not just the median — and cannot be gamed by hedging:

- **Banded rubric** (the outcome maps to discrete bands): primary `brier`, the multi-category Brier
  score over the bands, computed from the share of Monte-Carlo draws in each band; the logarithmic
  score is reported alongside. Set `"primary_metric": "brier"`.
- **Arithmetic / continuous rubric** (the outcome maps linearly onto 0-100, no bands): primary
  `crps`, the Continuous Ranked Probability Score of the empirical draw distribution. CRPS reduces to
  `|forecast - actual|` when the forecast is a point mass, so it *generalizes* absolute error rather
  than replacing it. Set `"primary_metric": "crps"`.

In both cases keep `"secondary_metrics": ["absolute_error"]` so the ledger's original metric is
always reported beside the proper score. `schelling compare` prints every metric.

> **Frozen rubrics are never edited.** The three questions sealed before D40
> (`Q-2026-USIRAN-STAGE2`, `Q-2026-IAEA-SEP`, `Q-2026-OPEC-SEP`) declare **no** `primary_metric`, so
> they keep `|median - actual|` as primary exactly as sealed — the proper scores are computed for
> them only as a secondary, labelled read. This template governs questions sealed from now on.

---

**Pre-registered `<DATE>`, before resolution (`<RESOLUTION DATE>`); final after `<RESOLUTION DATE>`.**
Fixed in advance so the score cannot be reverse-fit to the outcome. Referenced from
[FORECASTS.md](../FORECASTS.md).

**Binary criterion.** `<the exact yes/no event that counts as the question resolving>`

**Adjudicating sources (precedence order).** `<1. … 2. … 3. …; how genuine conflicts are handled>`

**Mapping rule.** `<how the real-world outcome maps onto the 0-100 continuum — the bands, or the
arithmetic formula>`

**Grading formula.** Primary: `<brier over the bands | CRPS of the draws>`. Secondary:
`score(r) = |r.ensemble.median - actual|` per sealed record on the 0-100 continuum. All sealed
records are scored (challenge, compromise, llm-judgment); the grade, its justification, and all
cited sources are published in FORECASTS.md at grading.

**Integrity checks before scoring.** `schelling verify` on every sealed record; the ledger's
OpenTimestamps proof checked with `ots verify` to confirm the commitment predates resolution.

**Final:** no edits to this rubric under any circumstances after `<RESOLUTION DATE>`.

```json
{
  "resolution_criteria": "<the exact yes/no event>",
  "adjudicating_sources": ["<source 1>", "<source 2>"],
  "outcome_mapping": "<bands, or the arithmetic mapping onto 0-100>",
  "grading_formula": "Primary <brier|crps>; secondary score(r) = |r.ensemble.median - actual| per sealed record on the 0-100 continuum.",
  "bands": [],
  "primary_metric": "brier",
  "secondary_metrics": ["absolute_error"]
}
```

For a banded question, fill `bands` with `{"lo", "hi", "label"}` entries tiling 0-100 and set
`"primary_metric": "brier"`. For an arithmetic question, leave `bands` empty and set
`"primary_metric": "crps"`.
