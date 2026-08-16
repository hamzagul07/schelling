# GRADING — Q-2026-USIRAN-STAGE2

**Pre-registered grading rubric.** Written 2026-07-22, *before* the 2026-08-31 resolution and fixed
in advance, so the score cannot be reverse-fit to the outcome. Referenced from
[FORECASTS.md](FORECASTS.md).

> **Revised 2026-07-22 (pre-resolution), ratified by Hassan as his pre-registration.** The bands now
> tile 0–100 completely and add explicit US-leaning and Iranian-leaning interim tiers, with a
> midpoint-default grading rule — so every possible outcome maps to exactly one band and the grade is
> deterministic absent cited deviation. **Final: no edits under any circumstances after 2026-08-31.**

The machine-readable `resolution_rubric` (schema: `schemas/question.py` → `ResolutionRubric`) is
embedded verbatim at the end of this file. For questions sealed *after* the rubric feature existed it
is embedded in the sealed game itself; the four US-Iran records were sealed before it existed, so for
them this committed document is the canonical embedded rubric (embedding it in the already-sealed game
would change the record bytes and break the seal, since the rubric is part of the record's game but
excluded from `inputs_hash`).

## Question

Will the US and Iran advance to MOU "stage two" by 31 August 2026 — and if so, what shape does the
resulting settlement take? The four sealed forecasts predict the **shape** on a 0–100 continuum, not
merely the binary, so the binary criterion below fixes *whether* a settlement exists and the mapping
rule places its *shape* on the scale.

## Continuum

Shape of a comprehensive US–Iran settlement, 0–100:

- **0** — maximal US/Israel terms (Iran capitulates: dismantlement, zero enrichment, intrusive
  verification, minimal sanctions relief).
- **50** — a balanced interim arrangement (mutual, reversible steps; partial relief for partial
  limits).
- **100** — maximal Iran terms (Iran retains full enrichment and program with broad sanctions relief
  and no new binding constraints).

## Binary resolution criterion

"Stage two" is **reached** iff, on or before **2026-08-31 23:59 UTC**, the US and Iran have *jointly
and publicly* confirmed entry into a second, negotiated phase, as defined by the 17 June MOU's staged
structure, beyond exploratory/stage-one talks — via a signed interim or framework agreement, or an
officially announced stage-two round with agreed terms. Exploratory talks, one-sided offers, and
unconfirmed leaks do **not** count. If stage two is not reached, the forecast is still scored: the
settlement's *shape as of the resolution date* is graded at the prevailing status-quo point per the
mapping rule.

## Adjudicating sources (precedence order)

1. Official US (State Department / White House) and Iranian (Ministry of Foreign Affairs / Supreme
   National Security Council) statements and published agreement texts.
2. IAEA Board of Governors documents and Director-General statements.
3. United Nations Security Council records.
4. Wire services of record (Reuters, Associated Press) corroborating 1–3.

Conflicts resolve to the most authoritative primary document; where sources genuinely conflict, the
outcome is graded at the midpoint of the defensible range and the disagreement is recorded.

## Mapping rule (real-world outcome → 0–100)

The grader reads the settlement terms actually in force on 2026-08-31 and places them in exactly one
band (the bands tile 0–100 with no gaps or overlaps):

| Real-world outcome | Continuum band |
|---|---:|
| Full Iranian capitulation | 0–10 |
| No agreement / talks collapsed / hostilities resumed (status quo of maximal pressure) | 11–30 |
| Interim or framework on largely US terms (long moratorium, minimal or heavily phased relief, intrusive verification) | 31–44 |
| Signed interim/framework with mutual, reversible balanced steps | 45–60 |
| Interim or framework on largely Iranian-leaning terms (short moratorium, substantial relief) | 61–69 |
| Comprehensive deal on largely Iranian terms (enrichment retained, broad relief) | 70–85 |
| Full US capitulation | 86–100 |

**Midpoint default.** Within a band, the grade defaults to the band midpoint; any deviation from the
midpoint must cite specific settlement terms in the justification paragraph.

**Canonical text.** The sealed game's continuum text is canonical; the anchors above summarize it;
where they differ, the sealed text governs.

## Grading formula

For each sealed record *r*: **score(*r*) = |*r*.ensemble.median − actual|** on the 0–100 continuum
(lower is better). All four sealed records (challenge / compromise × v1 / v2) are scored. The
challenge-vs-compromise comparison is the live, out-of-sample test of the DEU-backtest verdict (that
the compromise weighted mean wins). No blending, no post-hoc reweighting. The comparison metric is
|median − actual| per record; the grade integer, its justification, and all cited sources are
published in FORECASTS.md at grading.

## Integrity checks run before scoring

For every sealed record, before it is scored:

1. `schelling verify <record.json>` — recomputes the record's SHA-256 and matches it against the
   ledger, recomputes the inputs hash, and re-solves the embedded game to confirm the forecast
   reproduces byte-for-byte.
2. The ledger's OpenTimestamps proof in `ledger-proofs/` is checked with `ots verify` to confirm the
   commitment predates resolution. See the verification section of [FORECASTS.md](FORECASTS.md).

## Machine-readable rubric (canonical, embedded)

The exact `ResolutionRubric` object for this question — the machine-readable form of everything above,
byte-frozen with this pre-registration.

> **Provenance of the `bands` array — ratified by Hassan, 2026-07-22 (D24.4):** Bands array added
> 2026-07-22 as a structured restatement of the seven bands already committed in outcome_mapping —
> identical boundaries and meaning, no semantic change, added so the report renders the probability
> strip. The prose outcome_mapping and the sealed continuum text remain canonical; if the array and
> the prose ever disagree, the prose governs. Pre-resolution; rubric is excluded from inputs_hash so
> no sealed record, ledger entry, or timestamp is affected.

```json
{
  "resolution_criteria": "'Stage two' is reached iff, on or before 2026-08-31 23:59 UTC, the US and Iran have jointly and publicly confirmed entry into a second, negotiated phase, as defined by the 17 June MOU's staged structure, beyond exploratory/stage-one talks (a signed interim/framework agreement or an officially announced stage-two round with agreed terms). Exploratory talks, one-sided offers, and unconfirmed leaks do not count. If stage two is not reached, the settlement's shape as of the resolution date is still graded per the mapping rule.",
  "adjudicating_sources": [
    "Official US (State Dept / White House) and Iranian (MFA / SNSC) statements and published agreement texts",
    "IAEA Board of Governors documents and Director-General statements",
    "United Nations Security Council records",
    "Wire services of record (Reuters, Associated Press) corroborating the above"
  ],
  "outcome_mapping": "Place the settlement in force on 2026-08-31 in exactly one band (the bands tile 0-100 with no gaps or overlaps): full Iranian capitulation 0-10; no agreement / talks collapsed / hostilities resumed (status quo of maximal pressure) 11-30; interim or framework on largely US terms (long moratorium, minimal or heavily phased relief, intrusive verification) 31-44; signed interim/framework with mutual, reversible balanced steps 45-60; interim or framework on largely Iranian-leaning terms (short moratorium, substantial relief) 61-69; comprehensive deal on largely Iranian terms (enrichment retained, broad relief) 70-85; full US capitulation 86-100. Within a band the grade defaults to the band midpoint; any deviation must cite specific settlement terms in the justification. The sealed game's continuum text is canonical; these anchors summarize it; where they differ, the sealed text governs.",
  "grading_formula": "The comparison metric is |median - actual| per record; the grade integer, its justification, and all cited sources are published in FORECASTS.md at grading.",
  "bands": [
    {"lo": 0, "hi": 10, "label": "Full Iranian capitulation"},
    {"lo": 11, "hi": 30, "label": "No agreement / talks collapsed / hostilities resumed"},
    {"lo": 31, "hi": 44, "label": "Interim or framework on largely US terms"},
    {"lo": 45, "hi": 60, "label": "Signed interim/framework with mutual, reversible balanced steps"},
    {"lo": 61, "hi": 69, "label": "Interim or framework on largely Iranian-leaning terms"},
    {"lo": 70, "hi": 85, "label": "Comprehensive deal on largely Iranian terms"},
    {"lo": 86, "hi": 100, "label": "Full US capitulation"}
  ]
}
```

---

## Pre-resolution analyst note (2026-08-16)

**This note changes NO grading rule and no sealed value.** It records a reading *before* the outcome
is known, so it is on the record ex ante and cannot be reverse-fit after resolution. Every figure in
the two tables is COMPUTED from the sealed ledger medians and the committed band midpoints (by
`schelling.report.analyst_note`; a drift-guard test pins the tables to the ledger and the rubric) —
none is hand-typed. Like the rest of this file the note is excluded from `inputs_hash`, so no sealed
record, ledger entry, or OpenTimestamps proof is affected.

The four **plausible** bands are collapse (11–30), largely-US-terms (31–44), balanced (45–60) and
Iranian-leaning (61–69); the two full-capitulation poles and the comprehensive-Iranian-deal band are
set aside as implausible for this horizon. Under the midpoint-default rule the graded value in each
band is its midpoint.

**Table (a) — graded value and each record's error, per plausible band.**

| Plausible band | Graded (midpoint) | challenge v1 | challenge v2 | compromise v1 | compromise v2 | llm-judgment v2 | Closest |
|---|---:|---:|---:|---:|---:|---:|---|
| Collapse (11–30) | 20.5 | 14.076 | 8.907 | 21.136 | 18.943 | 20.500 | challenge v2 |
| US terms (31–44) | 37.5 | 2.924 | 8.093 | 4.136 | 1.943 | 3.500 | compromise v2 |
| Balanced (45–60) | 52.5 | 17.924 | 23.093 | 10.864 | 13.057 | 11.500 | compromise v1 |
| Iranian-leaning (61–69) | 65 | 30.424 | 35.593 | 23.364 | 25.557 | 24.000 | compromise v1 |

**Table (b) — does the v2-beats-v1 sourcing finding replicate, per band?**

| Plausible band | challenge: v1 err → v2 err | compromise: v1 err → v2 err | Sourcing (v2 beats v1?) |
|---|---|---|---|
| Collapse (11–30) | 14.076 → 8.907 (v2 wins) | 21.136 → 18.943 (v2 wins) | REPLICATES |
| US terms (31–44) | 2.924 → 8.093 (v1 wins) | 4.136 → 1.943 (v2 wins) | SPLIT |
| Balanced (45–60) | 17.924 → 23.093 (v1 wins) | 10.864 → 13.057 (v1 wins) | FAILS |
| Iranian-leaning (61–69) | 30.424 → 35.593 (v1 wins) | 23.364 → 25.557 (v1 wins) | FAILS |

**Reading (a).** The closest family flips across the plausible range. The challenge model — whose
lower, US-leaning median sits near the collapse band — is closest *only* if the talks collapse; the
compromise model is closest in every other plausible band (on its v2 record in the US-terms band, on
its v1 record in the balanced and Iranian-leaning bands). No sealed record lands in the balanced or
Iranian-leaning bands, so every model is far if the settlement tilts Iranian.

**Reading (b).** The v2-beats-v1 (sourced-beats-thin) finding from the graded `Q-2026-OPEC-SEP` cycle
**replicates here only at the low end**: if the talks collapse, both families' sourced v2 records beat
their thin v1 records. The US-terms band **splits** — the compromise v2 record wins, the challenge v1
record wins. In the balanced and Iranian-leaning bands the finding **fails**: the thin v1 records,
sitting higher on the scale, are closer. The sourcing revision pulled both models toward the US pole
(D10.4), which helps when the outcome is low and hurts when it is high. Nothing here is a forecast or
a grade — it is the ex-ante reading, placed on record so it exists before the outcome is known.
