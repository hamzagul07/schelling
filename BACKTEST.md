# BACKTEST.md — DEU benchmark (living document)

Deterministic backtest of the solver against **351** resolved issues from the DEU III (doi:10.34810/data53). Every issue is a point-estimate game solved deterministically; live search is off (a frozen historical benchmark, CLAUDE.md rule 7). Capabilities: sourced treaty-regime Council power (Session 10, D10.1).

## The gate (fixed in advance)

> **Gate v2 (Session 10, immovable):** with real capabilities and the reference point, the challenge solver must beat the equally-equipped weighted mean on DEU MAE. Any model change beyond restoring inputs is validated split-sample.

**Verdict: FAILED ❌.**

The primary challenge model (rp-anchored, Q=0.7 (tuned split-sample)) has MAE **26.83**. Baselines: capability x salience weighted mean = 22.99, median actor position = 28.37. It beats 1 of 2 baselines (loses to capability x salience weighted mean).

## Split-sample validation (item 4)

The rp-anchored challenge's **q** was tuned on 176 training issues (candidates 0.3, 0.5, 0.7, 0.9) → selected **0.7** (train MAE 27.58), then scored on 175 held-out issues: test MAE **26.07** vs the equally-equipped weighted mean **23.32**. On the held-out half the tuned model does NOT beat the weighted mean — the reference point is a real, non-overfit improvement, but still insufficient.

## Noise-floor oracle (DIAGNOSTIC, D11.0)

A deliberately flexible cross-validated model (linear-ridge:l=10, 5-fold, rich features incl. positions) scores MAE **23.84** — an estimate of the extractable-signal ceiling. The compromise mean scores **22.99**, so the gap is **-0.84**: the mean is **at/near the ceiling**. Even an optimistic flexible model does not beat the mean — there is essentially no signal beyond the influence-weighted average, which is why every model we have tried fails to beat it.

## Per-method error (full issue set)

| Method | Kind | MAE | RMSE | Median AE | Max AE |
|---|---|---:|---:|---:|---:|
| Solver — paper-faithful (dynamic R, Q=1, risk on) | solver | 27.94 | 39.76 | 20.00 | 100.00 |
| Solver — risk off | solver | 28.82 | 41.66 | 20.00 | 100.00 |
| Compromise — capability x salience weighted mean | baseline | 22.99 | 29.77 | 17.54 | 89.26 |
| Baseline — median actor position | baseline | 28.37 | 40.64 | 20.00 | 100.00 |
| R=dynamic, Q=1 | sweep | 27.94 | 39.76 | 20.00 | 100.00 |
| R=dynamic, Q=0.5 | sweep | 27.36 | 38.67 | 20.00 | 100.00 |
| R=fixed, Q=1 | sweep | 27.92 | 39.70 | 20.00 | 100.00 |
| R=fixed, Q=0.5 | sweep | 27.45 | 38.54 | 20.00 | 100.00 |
| Challenge — rp-anchored, Q=0.7 (tuned split-sample) ★ | solver | 26.83 | 38.51 | 20.00 | 100.00 |

★ = the primary config the gate is judged on. Lower is better; scale is 0-100.

## Worst issues (by the primary solver's absolute error)

| Issue | Proposal | Forecast | Actual | Error |
|---|---|---:|---:|---:|
| d00067i2 | tankers | 0.0 | 100.0 | 100.0 |
| d04209i2 | worktime | 100.0 | 0.0 | 100.0 |
| d04287i3 | vis | 100.0 | 0.0 | 100.0 |
| d05246i4 | custom | 0.0 | 100.0 | 100.0 |
| d160070i2 | Posting | 100.0 | 0.0 | 100.0 |
| d170226i1 | Non-cash | 100.0 | 0.0 | 100.0 |
| d96112i4 | choco | 0.0 | 100.0 | 100.0 |
| d98195i3 | socrates | 100.0 | 0.0 | 100.0 |
| n00127i3 | massinflux | 100.0 | 0.0 | 100.0 |
| n00250i2 | CMOsugar | 100.0 | 0.0 | 100.0 |

## Published DEU model error rates, for context

The most-cited finding in this literature (Achen 2006, in Thomson et al.'s DEU project) is that the influence- and salience-weighted mean of member-state positions predicts EU outcomes as well as or better than the more complex bargaining and procedural models. Bueno de Mesquita's own tests on Thomson's data (2011) reproduce this: his 'Old Model' — the expected-utility / challenge model our solver reconstructs — records a mean absolute error around 21-28 on the 0-100 scale, losing to the simple weighted mean (~12-19). Our full-set result sits in the same regime and shows the same ordering.

| Published model | Mean abs. error | Subset | Source |
|---|---:|---|---|
| Old Model (expected-utility / challenge) | 21.5 | 9 issues w/ resolve data | BdM 2011, Table 1 |
| Weighted mean, round 1 | 11.8 | 9 issues w/ resolve data | BdM 2011, Table 1 |
| Weighted median, round 1 | 29.4 | 9 issues w/ resolve data | BdM 2011, Table 1 |
| Old Model (expected-utility / challenge) | 28.2 | issues w/o recursion point | BdM 2011, Table 3 |
| Weighted mean, round 1 | 19.4 | issues w/o recursion point | BdM 2011, Table 3 |
| Weighted median, round 1 | 19.8 | issues w/o recursion point | BdM 2011, Table 3 |

These are **not** directly comparable to our numbers (different DEU version, issue subset, and capability/resolve handling); they are cited to show the regime and the known ordering, not as a like-for-like benchmark.

### Citations

- Bueno de Mesquita, B. (2011). A New Model for Predicting Policy Choices: Preliminary Tests. Conflict Management and Peace Science 28(1): 1-21. doi:10.1177/0738894210388127.
- Achen, C. H. (2006). Institutional realism and bargaining models. In Thomson, Stokman, Achen & Konig (eds.), The European Union Decides. Cambridge University Press. (Finds the influence- and-salience-weighted mean of member positions did as well or better than more complex models.)
- Arregui, J. & Perarnaud, C. (2021). A new dataset on legislative decision-making in the European Union: the DEU III dataset. Journal of European Public Policy. doi:10.34810/data53.

## Method notes

- **Capability (sourced, D10.1).** DEU records no capability, so each member state takes its Council power in the treaty regime in force at the issue's decision date (pre-Nice / Nice weighted votes; Lisbon-era population), rescaled so the strongest actor = 100; Commission/EP each take the largest member-state power (D10.3). The same table feeds the challenge solver AND the weighted-mean baseline — a fair fight.
- **Point estimates.** Each issue is point estimates, so Monte Carlo is degenerate (zero variance, D3.1); the harness solves each issue once deterministically. `--draws` (2000) is recorded for interface parity but does not affect the result (D9.3).
- **Determinism.** Dataset pinned by SHA-256 `0d75f0d2f3a96982…`; engine `0b979564c190`; seed 42. Same inputs → byte-identical record.

## Domain verdicts, side by side

| Domain | Benchmark | Verdict |
|---|---|---|
| Cooperative (EU legislative) | DEU III, 351 issues | **Compromise mean wins.** The challenge solver loses even fully equipped; the noise-floor oracle shows the mean is at the extractable-signal ceiling. |
| Coercive (interstate crises) | Coercive library | **PENDING.** The expert-coded coercive tables (Hong Kong 1985, Iran 1984, ...) are in paywalled books; the harness is built and waits on the printed inputs (D11.1). |

## Scheduled next: the ICB coercive benchmark

EU legislative bargaining is a highly cooperative, consensual setting — the one BdM (2011) notes his model handles *worst*. The challenge model is built for competitive, coercive politics. So regardless of this verdict, the next benchmark is the International Crisis Behavior (ICB) dataset — coercive interstate crises — where the mechanism should have its best shot. Whether it clears there decides far more than this cooperative case.

<!-- LEADERBOARD:START -->
## Successor search — the leaderboard (Session R1)

Pre-registered 40/30/30 split (seed 20260721: train 140, dev 105, TEST 106), committed before any fitting; **TEST scored once**. Each candidate must beat the compromise weighted mean on the untouched TEST split; MAE deltas carry a paired bootstrap 95% CI (seed 20260721).

| Candidate | Scored on | dev MAE (comp.) | TEST MAE | comp. MAE | Δ (95% CI) | beats? |
|---|---|---|---:|---:|---|:--:|
| Candidate A — status-quo gravity | TEST rp-issues | 24.96 (23.87) | 22.09 | 21.26 | +0.83 [-0.15, +1.91] | no |
| Candidate B — regime-aware settlement | TEST (all) | 24.86 (24.10) | 21.57 | 21.09 | +0.48 [-0.69, +1.76] | no |

**No candidate beats the compromise weighted mean on TEST.** Both point estimates are worse and both bootstrap CIs straddle zero — statistically indistinguishable from, but not better than, the mean. The compromise model remains the settlement model for DEU; nothing was sealed against the live US-Iran game. A negative result, pre-registered and honest.
<!-- LEADERBOARD:END -->
