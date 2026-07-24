# STATUS — Schelling forecasting engine

**As of 2026-07-24.** Generated from repository artifacts. One page: where everything stands, every
open gate with its threshold, and — at the end — the short list of things only a human can do.

## Engine

- **Version:** engine v1 (frozen; `schelling verify` re-solves every sealed record under the version
  it was sealed with — D39). Six forecasting models ship: `challenge`, `compromise`, and the four
  Phase C options `challenge-qre`, `nash`, `nash-ks`, `pce` (all additive; challenge/compromise
  paths byte-identical). Source: `src/schelling/mc/monte_carlo.py` (`KNOWN_MODELS`).
- **Determinism:** same seed + inputs → byte-identical `ForecastRecord`. 509 tests pass / 510
  collected, `mypy --strict` clean across the package, CI green on `main`. Source: `paper/EVIDENCE.md`
  (`E-TESTS`), CI.
- **Analysis layers:** proper scoring (Brier/log/CRPS), power indices (Shapley-Shubik, Banzhaf),
  Sobol global sensitivity — all read-only, no LLM produces a probability (CLAUDE.md rule 1).

## Sealed forecast ledger (14 records, 0 graded — all resolve in the future)

Source: `FORECASTS.md` (commit-reveal; record files are gitignored until reveal).

| Question | Records (model × vintage) | Resolution | Grading | Status |
|---|---|---|---|---|
| Q-2026-OPEC-SEP | challenge/compromise/llm-judgment × {v1-thin, v2-sourced} = 6 | 2026-08-05 | 2026-08-06 | sealed, awaiting resolution |
| Q-2026-USIRAN-STAGE2 | challenge/compromise × {v1, v2} + llm-judgment v2 = 5 | 2026-08-31 | 2026-08-31 | sealed, awaiting resolution |
| Q-2026-IAEA-SEP | challenge/compromise/llm-judgment × v1 = 3 | 2026-09-30 | 2026-09-30 | sealed, awaiting resolution |

Each question carries a pre-registered `GRADING-<id>.md` rubric (fixed before resolution, D17.1);
the ledger is externally anchored with OpenTimestamps (`ledger-proofs/`).

## Case library, canon, paper, site

- **Coercive case library:** `data/coercive-cases/` — China 2014 (KTAB, 2 tables, 60 rows, blind
  dual-entry **verified**); Japan 2017 (**scaffold, unverified**). No coercive case is yet verified
  toward the reading (see gates).
- **Concept canon:** 29 cards across 5 families (A–E). Source: `data/concepts/canon.md`. Concepts
  library only — never a source of real-world facts (CLAUDE.md rule 6).
- **Paper:** *Structure, Not Magic* — 7,079 words, abstract + 10 sections, every number E-tagged
  (`paper/EVIDENCE.md`). Assembled by `schelling paper-assemble` (`paper/DRAFT.md`). Preprint package
  ready in `paper/preprint/` (manuscript + SSRN metadata + 150-word summary + keywords).
- **Site:** 4 published pages (index, ledger, findings, paper) + 5 reports under `docs/`; regenerated
  by `schelling site build` and drift-checked in CI. Decisions logged: 199 (`DECISIONS.md`).

## Open gates (threshold → current state)

1. **DEU cooperative accuracy gate (Gate v2).** Threshold: the challenge model, fully equipped
   (sourced capabilities + reference point), must beat the capability×salience weighted mean on DEU
   MAE. → **CLOSED, negative.** Compromise mean wins; the noise-floor oracle puts the mean at the
   extractable-signal ceiling. Source: `BACKTEST.md`, `E-DEU-GATE`, `E-ORACLE-GAP`.
2. **Phase C solver gate.** Threshold: a new solver validates only if its DEU TEST MAE beats the
   compromise mean *and* the 95% bootstrap CI lies entirely below 0 (`docs/PHASE-C-GATE.md`). → **all
   four exploratory** (challenge-qre, nash, nash-ks, pce); PCE the near-miss (CI straddles 0). None
   sealed. Source: `BACKTEST.md` (Phase C leaderboard), `E-PHASEC-*`.
3. **Coercive reading — Model Three (MT-1.0).** Threshold: at the pre-registered **8-verified-case**
   coercive reading, MT-1.0 must beat the unadjusted compromise mean on MAE with paired bootstrap
   intervals (`specs/MT-1.0.md`, `src/schelling/cli.py:_READING_N = 8`). → **NOT FIRED** — the library
   holds 2 verified case-tables (China 2014), none coercive; blocked on paywalled inputs (D11.1).
4. **Live-ledger family comparison (`schelling compare`).** Threshold: refuse to rank
   challenge/compromise/llm-judgment until **10 graded** questions (`MIN_GRADED = 10`). → **0 graded**;
   exploratory, no ranking claimed. Advances only as the sealed questions resolve and are graded.

## BLOCKED ON HASSAN

Only items no machine can do, in deadline order. Everything else in this repository is already done
or will run mechanically once these unblock it.

1. **Grade Q-2026-OPEC-SEP — due 2026-08-06** (resolution 2026-08-05). *~30 min.*
   On/after 2026-08-05, read the OPEC Secretariat's published September-2026 collective adjustment in
   thousands of b/d (opec.org — the statement and its required-production table). Enter it as the
   actual outcome; the arithmetic grade in `GRADING-Q-2026-OPEC-SEP.md`
   (`grade = 50 + adjustment_kbd/600 × 50`, clamped) and `schelling verify` on the 6 sealed records
   then run mechanically; publish the grade in `FORECASTS.md` and re-anchor with `schelling stamp`.
   *Human because it requires reading a future real-world announcement and adjudicating sources.*

2. **Grade Q-2026-USIRAN-STAGE2 — due 2026-08-31.** *~30 min.*
   Determine whether the US and Iran advanced to MOU "stage two" by 2026-08-31 per the criterion and
   adjudicating sources in `GRADING-Q-2026-USIRAN-STAGE2.md`; enter the outcome, publish, verify,
   stamp.

3. **Grade Q-2026-IAEA-SEP — due 2026-09-30.** *~30 min.*
   Read the IAEA September outcome per `GRADING-Q-2026-IAEA-SEP.md`; enter, publish, verify, stamp.

4. **Confirm the author surname — before preprint submission.** *~1 min.*
   Replace `Hassan [surname]` in `paper/preprint/manuscript.md` and `paper/preprint/ssrn-metadata.md`
   with the full author name.

5. **Submit the preprint to SSRN — before submission target (no external deadline).** *~30 min.*
   Convert `paper/preprint/manuscript.md` to PDF (figures in `paper/preprint/figures/`), upload at
   https://ssrn.com → "Submit a paper", and fill the form from `paper/preprint/ssrn-metadata.md`.
   *Human because it needs an SSRN account, the upload, and accepting the terms.*

6. **Send the Scholz email — before/with submission (no external deadline).** *~15 min.*
   Confirm a current address for Jason Scholz (see the note in `docs/outreach/scholz-email.md`), fill
   the two placeholders, and send the text as written. Do not send to an unverified address.

7. **Acquire the coercive expert-coded tables — no deadline; gates the coercive reading.** *Hours per
   case.* Obtain the paywalled BDM coercive-case tables (e.g. Hong Kong 1985, Iran 1984) by purchase
   or library, then transcribe them blind-dual-entry into `data/coercive-cases/` toward the
   8-verified-case reading (`specs/MT-1.0.md`). *Human because the inputs are paywalled print and
   require purchase/library access plus human transcription and ratification.*
