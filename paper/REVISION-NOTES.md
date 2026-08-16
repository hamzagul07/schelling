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

**Status:** proposed 2026-08-16; not applied. Apply at the next revision, then reassemble and rebuild.
