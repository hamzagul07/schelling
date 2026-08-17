# Paper revision notes — proposed wording changes, NOT yet applied

Proposed edits for the **next** paper revision. The committed/sealed text is left unchanged now; each
item names the source file, the current wording, the problem, and a proposed replacement. Applying an
item means editing the section source, then reassembling `paper/DRAFT.md` (`schelling paper-assemble`)
and rebuilding the preprint (`schelling preprint build`).

---

## D58.2 — §8 (Ledger): "coherent within-question signal" overclaims given the directional confound

**Source:** `paper/draft/08-ledger.md` (assembled into `paper/DRAFT.md` and
`paper/preprint/manuscript.md`).

**Current wording (do not change now):**

> Within this single question, the better-sourced input vintage beat the thin one in every model
> family: the challenge solver's absolute error fell from the thin to the sourced vintage, the
> compromise mean's likewise, and the language-model structuring's from 8.000 to 0.000. **That is a
> coherent within-question signal that better inputs help** — of a piece with this paper's thesis that
> the structuring of the inputs, not the solution concept, is what carries these forecasts.

**Problem.** The bolded claim is stronger than one graded question supports. On `Q-2026-OPEC-SEP` the
sourcing revision moved every family's forecast **upward** and the realized outcome was an increase,
so "better inputs improve accuracy" is confounded with "the revision happened to move toward the
outcome" (see the directional caveat, D58.1, in `GRADING-Q-2026-USIRAN-STAGE2.md`). A single question
whose revision points one way cannot separate the two explanations.

**Proposed replacement:**

> Within this single question, the better-sourced input vintage was closer than the thin one in every
> model family — the challenge solver, the compromise mean, and the language-model structuring alike.
> One graded question cannot, however, separate "better inputs improve accuracy" from "the sourcing
> revision happened to move toward the realized outcome": here the revision moved every family's
> forecast upward and the outcome was an increase, so the two explanations are confounded. The result
> is consistent with — but does not on its own establish — this paper's thesis that the structuring of
> the inputs, not the solution concept, is what carries these forecasts. Separating the two requires
> graded questions on which the sourcing revision moves in different directions;
> `Q-2026-USIRAN-STAGE2`, where the revision moved forecasts downward, is pre-registered to supply
> that contrast.

---

## D60.1 — §3 (Fair fight): two factual corrections about the DEU benchmark

**Source:** `paper/draft/03-fair-fight.md` (assembled into `paper/DRAFT.md`).

**Problem.** §3 says "DEU records no capability data." That is correct but two clarifications should be
added, surfaced by the Session-60 reviewer investigation (docs/review/reviewer-package.md):

1. **The framework's third input is exogenous.** The exchange-model literature describes the DEU
   framework as "positions, saliences, and capabilities," which can read as though the dataset codes
   capability. It does not: every wave records only position and salience per actor; the capability
   input is supplied **exogenously** (Council voting weights), not as a coded column. §3 should say so
   explicitly, so the reader does not infer a coded capability variable.
2. **The 351 issues already span all three waves.** The repo dataset is the combined **DEU I + II +
   III** (141 proposals / 364 issues, 1999–2019; 351 scored), not a single wave. §3 (or §9) should
   state this, because it establishes that **n cannot be increased by adding earlier waves** — they
   are already in — so the predictability-ceiling limit is a property of the benchmark, not a
   sample-size problem. The paired-MAE minimum detectable effect at n = 351 (~3.04 scale units) is
   worth stating alongside, and belongs in the abstract.

**Status:** proposed 2026-08-17; not applied. Sealed text unchanged. Apply at the next revision, then
reassemble `DRAFT.md` and rebuild the preprint.

**Status:** proposed 2026-08-16; not applied. Apply at the next revision, then reassemble and rebuild.

---

## D63.0 — §4.1 (The operator, not the dynamics): slated for rewrite under the regime decomposition

**Source:** `paper/draft/04-successor-search.md`, §4.1 (assembled into `paper/DRAFT.md` and the
preprint manuscript).

**Context.** v7 (D63) applied only a *minimal* fix to §4.1: the operator explanation is now framed
as a hypothesis these results are consistent with rather than one they demonstrate, and the section
states that the direct mechanism evidence is the two-game median-lock probe (n = 2), not the
351-issue MAE comparison. That is a holding action, not the section's final form.

**Problem the minimal fix does not resolve.** The external reviewer has separately identified a
**centrality confound**: the "median operator locks, mean operator smooths" account cannot, on the
present evidence, be cleanly separated from the fact that the mean is simply a measure of central
tendency well matched to a benchmark whose outcomes cluster centrally. The operator-vs-dynamics claim
therefore rests on n = 2 live games and remains confounded with issue centrality.

**Plan.** §4.1 is slated for a **full rewrite under the regime-decomposition work** (Session 62 gate
and its follow-on): the rewrite should either supply a centrality-controlled test of the median-lock
mechanism or downgrade the operator claim to an explicitly caveated, named result. Do **not** treat
the current §4.1 wording as settled.

**Status:** proposed 2026-08-17; the minimal v7 reframe is applied, the full rewrite is not. Revisit
with the regime decomposition.
