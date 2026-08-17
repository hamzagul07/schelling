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

---

## D62 — Regime decomposition: a negative result (POST-HOC; nothing sealed changed)

All numbers below regenerate deterministically from `docs/review/regime-decomposition.py`
(committed, Q = 0.700, seed 62). POST-HOC and TEST-touching — hypothesis generation, not evidence.
The decomposition asked whether the pole/middle split the reviewer found is *politics* (a signal the
mechanism captures) or *structure* (a coding artifact). Answer: **structure plus a scoring-rule
artifact; there is no recoverable regime signal that beats the mean.**

**What the cut found.**
- **Classification (ex ante, from the issue spec):** of 351 issues, **binary = 90 (26%)**, **graded =
  261 (74%)** — binary = 2 named alternatives in the Policy Scales, graded ≥ 3 (53 post-2016 issues
  lack a scales entry and fall back to "any interior elicited position"). Pole outcomes are 66%
  binary vs a 26% base rate, so "pole" is heavily confounded with binary issue structure.
- **2×2 (operator × position vintage):** mean-init **22.99** (best of the four), mean-conv 23.90,
  med-init 28.42, med-conv (= challenge) **26.83**. The challenge's +3.84 penalty decomposes into
  **operator +2.93** (median vs mean on the same converged positions) and **dynamics +0.90, ns**
  (CI [−0.21, +1.99]). The dynamics add no information anywhere; the operator is the culprit.
- **Proper scores (each model's own ensemble):** on graded poles the challenge's CRPS is *worse*
  (25.5 vs 22.0) and its **resolution is tied** (0.084 vs 0.086 on P(≥85)); the .30 hit rate is a
  **commitment artifact** (the challenge calls a pole 48% of the time, right 44%, base rate 31%) — the
  same pattern on binary poles.
- **Robustness:** the +3.84 gap holds under a dossier-clustered bootstrap (CI [+1.65, +6.08], 137
  clusters); trimming each model's top-5/10% blowups drops the gap to **+2.54 / +1.42 — below the MDE
  3.04**, so the challenge's loss is substantially a tail phenomenon and the defensible claim is
  "does not beat the mean," not "is worse."
- **Attacks (post-hoc, in-sample):** convex combination, shrink-to-mean, shrink-to-50 all bottom out
  at the mean's 22.99 (best convex weight is 0.95 on the mean); linear recalibration is worse (23.38);
  the OLS slope of outcome on the weighted mean is **0.776, CI [0.627, 0.925]** (< 1, so the mean is
  mildly too extreme under squared loss, but no transform helps MAE).
- **Payoff curves:** routing each issue to its regime's best model, **even at perfect classification**,
  caps at 21.75 (pole/middle) or 22.73 (binary/graded) MAE — break-even needs 80% / 94% accuracy and
  an MDE-sized gain is **unreachable at any accuracy**. The two-model oracle bound (16.66) is reachable
  only by *per-issue* selection, which the residual probe (R² ≈ 0) already showed is not learnable.

### D62 item 4 — §4 correction: the regime model *blended where selection was required*

**Source:** `paper/draft/04-successor-search.md`, §4 (the regime-model paragraph).

**Current wording (do not change until the §4.1/regime rewrite):** "…the fitted model collapsed —
assigning roughly five-sixths of its weight to the compromise component… We read this as evidence
that the structural features available in these data carry no exploitable regime signal *within* the
domain…"

**Problem:** "no exploitable regime signal" is too strong. A weak signal exists — the fitted regime
classifier separates the structural regimes at **AUC ≈ 0.665**, above chance. The R1 model failed not
because the signal is absent but because it **blended** (soft-weighted its three components) where
**selection** (hard routing) was required, and with full freedom it put ~5/6 weight on the mean.

**Proposed replacement:** "The more informative result is *how* the regime model failed: it **blended
where selection was required** — granted freedom to weight its three components it put roughly
five-sixths of its weight on the compromise and treated the rest as noise. This shows that *soft
blending* of regime components does not help; it does not show that no regime signal exists. A weak
one does — the fitted regime classifier separates the structural regimes at AUC ≈ 0.665. But the
signal is unexploitable for accuracy: routing each issue to its regime's best model, even at *perfect*
classification, cannot beat the weighted mean by the benchmark's minimum detectable effect (pole/middle
routing caps at 21.8 MAE against the mean's 23.0; an MDE-sized gain is unreachable at any accuracy).
The regime hypothesis thus survives only in the cross-domain form Section 7 tests; within this domain
the signal is real but too weak for any routing to convert into a detectable gain."

### D62 item 7 — retire operator-smoothness as a frame; keep it as a caveated named result

**Source:** `paper/draft/04-successor-search.md`, §4.1.

**Keep (named result, now on 351 issues):** the 2×2 establishes that the **median operator is +2.93
MAE worse than the mean operator on identical converged positions**, and that the dynamics are inert
(+0.90, ns) — so "the operator, not the dynamics, drives the loss" graduates from the n = 2 live-game
probe to the full benchmark.

**Retire (causal frame):** the **"smoothness / median-lock" mechanism** — median snaps, mean smooths
— as the *explanation*. It rests on the n = 2 sensitivity probe and is **confounded with centrality**:
the mean is a central-tendency estimator and 69% of DEU outcomes are central (middle), so "mean beats
median" may reflect central clustering of outcomes rather than a lock/smoothness mechanism. §4.1
should state the operator result and the centrality confound, and drop median-lock as the causal
story (the D63.0 note above already flags §4.1 for this rewrite and records the reviewer's confound).

### D62 item D — the ceiling claim, sharpest available form

For the next revision, the ceiling should be stated as follows (mean-error loss, this domain and input
set): **the capability×salience weighted mean of the raw inputs is the best point forecast obtainable
from these inputs, across every structural cell.** Grounds: (1) the mean dominates the challenge by
every proper score in every cell (CRPS, Brier, resolution); (2) the challenge's pole advantage is a
commitment artifact uniform across structure (~4-unit point edge on poles, both below their cells'
MDE, no resolution gain); (3) the median operator discards ~2.93 MAE that a mean over the same settled
positions recovers, but that recovery still does not beat the raw compromise, and the dynamics are
inert; (4) no regime routing beats the mean by the MDE at any classifier accuracy. The per-issue
oracle bound (16.66) is not a counterexample — it is reachable only by issue-level selection, which
the residual probe (R² ≈ 0) showed is not learnable from structure.

**Status:** proposed 2026-08-17; not applied. The paper text is unchanged this session. Apply items 4,
7, D at the §4/§4.1 rewrite, then reassemble `DRAFT.md` and rebuild the preprint.
