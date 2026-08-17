# Pre-registration — structural (binary vs graded) issue classifier

**Registered:** 2026-08-17 (Session 62, D62.1). **Status:** committed *before* any classifier code
exists. This document is the pre-commitment; the append-only git history certifies that it precedes
any implementation or run, exactly as `src/schelling/backtest/deu3_split.json` certified the R1
train/dev/test split. **No classifier is run in the session that registers this.**

## Why this exists, and what was dropped

The Session 62 regime decomposition (see `docs/review/regime-decomposition.py` and the D62
REVISION-NOTES entry) split the DEU benchmark into **binary** issues (2 named policy alternatives) and
**graded** issues (≥ 3). That structural axis explains most of the pole/middle pattern the reviewer
found. Two classifier targets were considered; they mean different things and are pre-registered — or
not — separately.

- **Structural target (REGISTERED here).** Can a language model, reading only an issue's *specification
  text*, predict **binary vs graded**? This is a property of the **question**, not the outcome, so
  contamination risk is low. It validates that the binary/graded distinction is textually real and not
  an artifact of our coding.
- **Political target (DROPPED as mooted).** "Within graded issues, can polarized vs consensual
  *outcomes* be predicted?" This presupposes a political signal the mechanism could exploit. The A.5
  proper-score analysis showed there is none to exploit — on graded poles the challenge model has **no
  resolution advantage** over the mean (tied Brier resolution, worse CRPS); its apparent edge is a
  commitment artifact. With no recoverable political signal, the target is not worth the (higher)
  contamination risk of an outcome-predicting probe. It is not registered.

## Registered hypothesis (structural)

**H1.** A language model reading only the Policy Scales issue text (the numbered issue statement and
its alternative descriptions), with all outcome, position, salience and reference-point information
withheld, classifies issues as binary vs graded at **≥ 75% balanced accuracy** on the clean evaluation
set defined below.

- **Label (ground truth):** binary = exactly two named alternatives in the Policy Scales entry; graded
  = three or more. The count is computed mechanically by `parse_poles()` in
  `docs/review/regime-decomposition.py`; issues without a Policy Scales entry are excluded from H1
  (they are not label-clean).
- **Metric:** balanced accuracy (mean of per-class recall), to neutralise the 26/74 class imbalance.
- **Decision:** H1 is confirmed iff balanced accuracy ≥ 0.75 on the clean set after the contamination
  controls below; otherwise it is rejected. The threshold is fixed now and will not be moved.

## Contamination controls (lighter than the political probe would need, because risk is low)

Applied in order; each issue must survive all three to enter the clean evaluation set.

1. **Per-issue recall probing with drops.** Before classifying, probe whether the model already
   recognises the specific DEU dossier/issue (ask it to identify or complete the dossier from a stem).
   **Drop** any issue the model demonstrably recalls; it cannot be scored as a structural inference.
2. **Model-cutoff restriction.** Prefer issues whose dossiers postdate the model's training cutoff;
   report accuracy separately for the post-cutoff subset (the cleanest) and the full clean set.
3. **Perturbation control.** Paraphrase / perturb the issue text (rename entities, reword alternatives)
   without changing the alternative *count*. Accuracy must survive perturbation; a large drop indicates
   string-matching to memorised text rather than reading structure. Report perturbed accuracy as the
   headline.

## Pre-computed payoff (registered so the result cannot be re-spun)

Even a **perfect** structural classifier cannot turn this signal into a detectable forecasting gain.
Routing binary → challenge and graded → mean, the expected MAE at classifier accuracy α is linear
from E(0) = 27.09 to **E(1) = 22.73**, against the weighted mean's **22.99**:

- **break-even** (E = mean) requires **α ≈ 0.94**;
- **MDE-beating** (E = mean − 3.04) requires **α ≈ 1.64 — unreachable at any accuracy**.

Therefore H1 is registered as a **descriptive validation** of the structural distinction, **not** as a
route to beating the mean. Confirming H1 (text predicts structure) and confirming the payoff ceiling
(structure cannot beat the mean) are compatible and are the expected joint outcome. Numbers regenerate
from `docs/review/regime-decomposition.py` (PAYOFF section).

## What would falsify the surrounding claim

If, contrary to the payoff analysis, some *learned* per-issue router (not the perfect-accuracy bound
above) beat the weighted mean by ≥ MDE on a held-out split, the "no recoverable regime signal"
conclusion would be wrong. The residual probe (R² ≈ 0, CI spanning zero) already argues against this;
H1's structural classifier does not test it and is not claimed to.
