# GRADING — Q-2026-USIRAN-STAGE2

**Pre-registered grading rubric.** Written 2026-07-22, *before* the 2026-08-31 resolution and fixed
in advance, so the score cannot be reverse-fit to the outcome. This is the human-readable companion
to the machine-readable `resolution_rubric` embedded in the sealed game (schema:
`schemas/question.py` → `ResolutionRubric`). Referenced from [FORECASTS.md](FORECASTS.md).

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
and publicly* confirmed entry into a second, negotiated phase beyond exploratory/stage-one talks —
via a signed interim or framework agreement, or an officially announced stage-two round with agreed
terms. Exploratory talks, one-sided offers, and unconfirmed leaks do **not** count. If stage two is
not reached, the forecast is still scored: the settlement's *shape as of the resolution date* is
graded at the prevailing status-quo point per the mapping rule.

## Adjudicating sources (precedence order)

1. Official US (State Department / White House) and Iranian (Ministry of Foreign Affairs / Supreme
   National Security Council) statements and published agreement texts.
2. IAEA Board of Governors documents and Director-General statements.
3. United Nations Security Council records.
4. Wire services of record (Reuters, Associated Press) corroborating 1–3.

Conflicts resolve to the most authoritative primary document; where sources genuinely conflict, the
outcome is graded at the midpoint of the defensible range and the disagreement is recorded.

## Mapping rule (real-world outcome → 0–100)

The grader reads the settlement terms actually in force on 2026-08-31 and places them on the
continuum by these anchors, recording the single integer chosen and a one-paragraph justification
citing the sources above:

| Real-world outcome | Continuum band |
|---|---:|
| Full Iranian capitulation | ≤ 10 |
| No agreement / talks collapsed to the maximal-pressure status quo ante | 15–30 |
| Signed interim/framework with mutual, reversible steps | 45–60 |
| Comprehensive deal on largely Iranian terms (enrichment retained, broad relief) | 70–85 |
| Full US capitulation | ≥ 90 |

## Grading formula

For each sealed record *r*: **score(*r*) = |*r*.ensemble.median − actual|** on the 0–100 continuum
(lower is better). All four sealed records (challenge / compromise × v1 / v2) are scored. The
challenge-vs-compromise comparison is the live, out-of-sample test of the DEU-backtest verdict (that
the compromise weighted mean wins). No blending, no post-hoc reweighting; a method comparison ties
break by the smaller |median − actual|.

## Integrity checks run before scoring

For every sealed record, before it is scored:

1. `schelling verify <record.json>` — recomputes the record's SHA-256 and matches it against the
   ledger, recomputes the inputs hash, and re-solves the embedded game to confirm the forecast
   reproduces byte-for-byte.
2. The ledger's OpenTimestamps proof in `ledger-proofs/` is checked with `ots verify` to confirm the
   commitment predates resolution. See the verification section of [FORECASTS.md](FORECASTS.md).
