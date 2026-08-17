# Reviewer data package — DEU benchmark

**A response to the reviewer's data requests. Everything here is POST-HOC and EXPLORATORY** — none
of it was pre-registered, none of it changes a sealed forecast, a grading rule, or the paper's text.
All figures are computed from the committed DEU III dataset (`data/deu/Dataset_DEU_III.csv`) and the
solver/harness; the per-issue table regenerates via `schelling.backtest.review`. Where the data
contradicts a hypothesis we say so; where it supports the critique we say that too.

Two models throughout: **challenge** = the paper's primary reconstruction (rp-anchored, Q = 0.7
tuned split-sample, sourced capability); **compromise** = the capability × salience weighted mean.
n = 351 scored issues.

---

## 0. The headline correction (a property of the benchmark)

- The repo dataset is **already DEU I + II + III combined**: 141 proposals / **364 controversial
  issues, 1999–2019** (69 EU-15 dossiers = DEU I, 56 EU-27 = DEU II, 16 EU-28 = DEU III); **351 are
  scored** after dropping issues without a usable outcome.
- **No wave records expert-coded capability.** Every wave records position and salience per actor
  (`p<actor>`, `s<actor>`), plus a reference point (`rp`) and outcome (`out`) per issue — no
  capability/influence/power column. The exchange-model framework's "third input" (capability) is
  supplied **exogenously** as Council voting weights, not a coded column.
- **Consequence:** n cannot be increased by adding earlier waves — they are already in. The power
  limit is therefore a **property of the benchmark**, not a fixable sample-size problem.
- **Minimum detectable effect (MDE)** on a paired MAE difference at n = 351, 80 % power, α = 0.05
  two-sided: **≈ 3.04 scale units** (paired-difference sd ≈ 20.3). Effects smaller than ~3 units are
  undetectable at this benchmark's size and cannot be made detectable with more data. **This number
  belongs in the abstract.**

---

## 1. Per-issue paired differences (the reviewer's priority)

Attached: **`deu-paired-differences.csv`** — one row per scored issue (issue id, dossier, procedure,
n_actors, outcome, reference point, challenge forecast, compromise forecast, challenge AE,
compromise AE, paired difference challenge − compromise, winner).

**Summary (paired, same 351 issues):**

| Criterion | Challenge | Compromise | Verdict |
|---|---:|---:|---|
| Mean AE | 26.83 | 22.99 | compromise, **Δ = +3.84, 95 % CI [+1.66, +6.01]** (significant, above MDE) |
| Median AE | 20.00 | 17.54 | Δ = +2.46, **95 % CI [−2.34, +4.17]** — **not significant** |
| Hit rate \|err\| ≤ 5 | **0.291** | 0.171 | **challenge wins** |
| Hit rate \|err\| ≤ 10 | **0.407** | 0.308 | **challenge wins** |
| Hit rate \|err\| ≤ 20 | 0.547 | 0.538 | tie |
| CRPS (weighted-empirical) | 18.38 | 18.14 | tie (compromise +0.24) |
| Issues won | 157 | 194 | sign test **p = 0.055** (borderline) |

- **Sign test:** challenge wins 157, compromise wins 194, 0 ties; two-sided sign-test p = **0.055** —
  the compromise's edge in issues-won is *borderline, not significant*.
- **CRPS on DEU.** Each model's forecast is a **point**, so CRPS reduces exactly to absolute error
  (CRPS = MAE: 26.83 / 22.99). The table's CRPS is the *distributional* alternative — CRPS of the
  capability×salience-weighted empirical distribution of positions — where the two models are
  **essentially tied** (18.38 vs 18.14).
- **AE distribution by 10-wide bin** (reconstructs the error histograms, Figs 1/2):

  | AE bin | 0–10 | 10–20 | 20–30 | 30–40 | 40–50 | 50–60 | 60–70 | 70–80 | 80–90 | 90–100 |
  |---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
  | challenge | 116 | 50 | 50 | 30 | 25 | 35 | 13 | 7 | 6 | 19 |
  | compromise | 108 | 81 | 61 | 39 | 25 | 20 | 8 | 7 | 2 | 0 |

  The challenge is **more bimodal**: more exact hits (116 vs 108 in 0–10) *and* fatter tails (45
  issues ≥ 60 vs 17). The fat tail is what inflates its mean AE while its hit-rate stays high.

**Does the challenge model win on any criterion? Plainly: yes.** It wins on the tight-hit criteria
(≤ 5 and ≤ 10), ties on median AE, ties on CRPS, and its issues-won deficit is not significant. It
loses, clearly and above the MDE, **only under mean absolute error** — a tail-sensitive loss. The
paper's headline (compromise beats challenge) is therefore **real but loss-function-specific**: it
holds under MAE and fails or ties under every other criterion tested. This *supports* the reviewer's
suspicion that the single-loss headline oversells a robust conclusion.

---

## 2. Reconstruction and evaluation robustness (answering "you implemented it wrong" / "set up favourably")

Two separate grids, reported separately because they answer different objections. In **both**, the
challenge never beats the compromise mean.

### (A) Reconstruction-reading ambiguities — §2. Answers "you implemented it wrong."

The four §2 ambiguities and their status:

| # | Ambiguity | Current reading | Alternative | Enumerable? |
|---|---|---|---|---|
| a | Security superscript (A2) | `adversary` (column sum) | `own` (row sum) | **yes** (config flag) |
| b | Compromise-octant sign (A3) | follows figure 6 | the contradictory *text* clause | no — text is under-determined |
| c | Octant boundaries (A3/A4) | figure-6 sign/magnitude rules | — | no — paper gives no competing inequalities |
| d | Proposal-selection ordering (A4) | most-enforceable first | least-movement first | **yes** |

**k = 2** cleanly-enumerable readings (a, d) → 4 combinations run on DEU. (b) and (c) are
figure-resolved with no competing formulation to enumerate (D2.7/D2.9).

| security_mode | proposal_order | challenge MAE | beats mean (22.99)? |
|---|---|---:|---|
| adversary | enforceable | **26.83** | no |
| adversary | least_move | 27.07 | no |
| own | enforceable | 28.04 | no |
| own | least_move | 28.36 | no |

**Across all 4 defensible reconstruction readings, no reading beats the weighted mean** (best 26.83,
still +3.84 above it). *This sentence belongs in the abstract.*

### (B) Evaluation-configuration knobs. Answers "your evaluation was set up favourably."

**k = 8** evaluation knobs: capability (equal/sourced), reference point (on/off), Q (tuned/1.0),
range mode (dynamic/fixed), apply-risk (on/off), conflict-resolves (off/on), min-actors (3/2), and
issue set. A 2⁵ sweep over the five solver/evaluation knobs × 2 capability settings = **32
configurations**:

- The challenge beats the compromise mean in **0 of 32** configurations.
- The **lowest** challenge MAE (26.83) occurs at the paper's *own* config (sourced, rp, dynamic,
  risk-on, conflict-off) — i.e. the evaluation was set up **favourably to the challenge**, and it
  still lost by 3.84. The evaluation-favorability objection fails against the data.

### Ablation ladder (marginal contribution of each layer, MAE, n = 351)

| Layer | MAE | Marginal vs previous |
|---|---:|---|
| constant (grand median of outcomes) | 27.96 | — |
| reference point alone | 44.34 | −16.38 (rp alone is a poor predictor) |
| unweighted mean of positions | 23.63 | **+20.71 (this is where the accuracy is)** |
| salience-weighted mean | 23.64 | +0.01 [−0.70, +0.72] — **nothing** |
| capability × salience weighted mean | 22.99 | +0.65 [−0.13, +1.42] — not significant |
| challenge dynamics (rp-anchored median) | 26.83 | **−3.84 [−5.97, −1.70] — the dynamics HURT** |

The plain mean of positions carries the accuracy; salience and capability weighting add nothing
detectable (both marginals below the MDE); the challenge dynamics *subtract* 3.84 (significant).

### The missing 2×2 cell (mean vs median × initial vs converged)

| | initial positions | converged positions |
|---|---:|---:|
| **mean** | 22.99 | **23.90** (missing cell, now filled) |
| **median** | 28.37 | 26.83 |

Mean-on-converged (23.90) vs mean-on-initial (22.99): Δ = +0.90, 95 % CI **[−0.19, +2.02]** — the
dynamics do **not** significantly move the mean. Mean-on-converged vs median-on-converged: Δ = −2.93,
CI [−4.82, −1.03] — the **operator** (median vs mean) is significant. **Reading: the dynamics are
approximately inert; the operator is most of the story** — not "the dynamics destroy information."

### Capability-proxy sweep (`schelling power`, validated on EEC-6 / UNSC)

MAE under five capability proxies (compromise / challenge):

| Proxy | compromise MAE | challenge MAE |
|---|---:|---:|
| treaty voting weights (sourced) | **22.99** | **26.83** |
| Shapley–Shubik | 23.05 | 28.45 |
| Banzhaf | 23.08 | 28.18 |
| population | 23.14 | 28.18 |
| equal | 23.64 | 28.19 |

Range: compromise **[22.99, 23.64]** (spread 0.65), challenge **[26.83, 28.45]** (spread 1.62) — both
below the MDE. The capability proxy barely matters, and the challenge loses under every one. (GDP is
not in the repo; population is the available size proxy — and the spread already shows the proxy
choice cannot change the conclusion.)

---

## 3. The oracle / residual probe (the "no headroom above the mean" result)

**Oracle spec, verbatim** (`src/schelling/backtest/oracle.py`):

- **Model family:** kernel ridge regression (RBF kernel) *or* linear ridge with an un-penalised
  intercept, best-of-both selected by CV. The linear ridge takes the weighted mean as a feature, so
  the oracle is a valid **upper bound** — it can always fall back to "just use wmean".
- **Features (18):** `wmean` (capability×salience weighted mean), `median(p)`, `mean(p)`, `min(p)`,
  `max(p)`, `std(p)`, weighted quantiles q10/q25/q50/q75/q90, `gini(weights)`, `herfindahl(weights)`,
  `polarization`, `n_actors`, `procedure==COD` indicator, `rp`, `rp − wmean`.
- **CV protocol:** seeded 5-fold (seed 20260721), fold = seeded permutation mod folds; hyperparameters
  γ ∈ {0.01, 0.03, 0.1, 0.3}, λ ∈ {0.3, 1, 3, 10} chosen by the **same** CV (in-sample selection —
  deliberately optimistic); scored by MAE. **wmean is already a feature.**

**Residual reframing (cleaner, at the reviewer's request).** We fit the same learner family to the
**residual** `y − wmean` under the same seeded CV, and report cross-validated R²:

> **CV R² of the residual = −0.029, 95 % bootstrap CI [−0.090, +0.021].**

Indistinguishable from zero (slightly negative). **Mechanism (why this is the right direction):**
because wmean is already a feature, ridge shrinkage biases its coefficient *away from 1* when fitting
y, which flatters the flexible model; fitting the *residual* instead shrinks toward **zero — which is
exactly the baseline** — so the residual design is **conservative in the correct direction**. The
offsetting optimism is the in-sample hyperparameter selection (which flatters the learner). Even so,
R² ≤ 0: **the flexible learner extracts no signal beyond the weighted mean.** The mean sits at the
extractable-signal ceiling of these inputs.

---

## 4. Feasibility of running the formalizer over DEU (investigation only — nothing built or run)

Can the formalizer path (`schelling formalize --search`) run over DEU issues end to end?

- **What a DEU issue must become.** The formalizer consumes a free-text situation and emits a
  `DraftGameSpec` — actors, each with a position, salience and capability on a 0–100 continuum, plus
  a stated continuum and cited sources. A DEU issue already *is* a coded game (positions, saliences,
  outcome), so a formalizer run would test whether the model can **reconstruct that coded game from
  the issue's text** — the elicitation step the paper credits but never directly evaluates.
- **Does the dataset carry enough text? No — not machine-readably.** The CSV's `issues` column is a
  **count**, not a description; the only text is a short dossier name (`prname`, e.g. "documents").
  The issue narratives and the 0–100 policy-scale endpoints live in a **separate Policy Scales
  Word document**, not linked per CSV row. So a per-issue formalizer run would first need a manual
  extraction pass to turn each issue into a situation text — the dataset does not supply it.
- **Cost / time.** Each `formalize --search` call is one LLM call plus ≤ 6 web searches — on the
  order of $0.10–$0.50 and tens of seconds. 351 issues → roughly **$35–$175 and a few hours** of
  wall-clock (serial), before any solving.
- **Contamination risk — the decisive problem.** DEU outcomes are **published** (the book *The
  European Union Decides* and the Dataverse datasets), so the coded positions/saliences/outcomes are
  **plausibly in the model's training data**. A formalizer run could then **recall** the coded game
  rather than reconstruct it from evidence — the reconstruction would be contaminated and its success
  uninterpretable.
- **A contamination test to pre-commit BEFORE any run:**
  1. **Direct recall probing, per issue.** Before formalizing, ask the model (no search) to state the
     dataset/proposal/issue and its coded values. Score recall; **drop every issue the model
     recalls** from the reconstruction evaluation. Pre-register the recall prompt and the drop rule.
  2. **Model-cutoff strategy.** Restrict the evaluation to issues whose dossiers post-date the model's
     training cutoff where that can be established; report coverage honestly (DEU III's newest
     dossiers, 2016–2019, are the only candidates and may still be in-corpus).
  3. **Perturbation control.** Re-run on issues with lightly perturbed/anonymised text (renamed
     actors, shifted numbers); a model that reconstructs from evidence should be robust, a model that
     recalls should degrade — the gap estimates the contamination.
  Pre-commit all three (prompts, drop rules, thresholds) before a single live call.

---

## 5. Where the data supports vs contradicts the critique

**Supports the critique:**
- The compromise-beats-challenge headline is **loss-function-specific** — real under MAE, a tie or a
  loss under median AE, hit-rate, and CRPS. A single-loss headline oversells it.
- §3's "26.83 vs 22.99" is reported without an interval; the paired CI is **[+1.66, +6.01]** and
  should be printed.
- The benchmark's MDE (~3.04) is a real resolution floor that belongs in the abstract.

**Contradicts the critique:**
- "You implemented it wrong" — no defensible reconstruction reading beats the mean (Grid A).
- "Your evaluation was set up favourably" — no evaluation config beats the mean, and the paper's own
  config is the challenge's best case (Grid B); the capability proxy barely matters (item 5).
- "More data would fix the power limit" — the waves are already combined; n cannot grow.
- "There is headroom a better model could exploit" — the residual R² is ≤ 0; there is none.
