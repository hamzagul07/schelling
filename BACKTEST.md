# BACKTEST.md — DEU benchmark

Deterministic backtest of the solver against **351** resolved issues from the DEU III (doi:10.34810/data53). Every issue is a point-estimate game solved deterministically; live search is off (a frozen historical benchmark, CLAUDE.md rule 7).

## The gate (fixed in advance)

> The solver (paper-faithful config) must beat **both** naive baselines — the capability x salience weighted mean and the median actor position — on MAE across the full issue set. If it does not, the result is written up honestly here.

**Verdict: FAILED ❌.**

The solver's MAE is **28.31**. Baselines: capability x salience weighted mean = 23.64, median actor position = 28.37. It beats 1 of 2 baselines (loses to capability x salience weighted mean).

## Per-method error (full issue set)

| Method | Kind | MAE | RMSE | Median AE | Max AE |
|---|---|---:|---:|---:|---:|
| Solver — paper-faithful (dynamic R, Q=1, risk on) ★ | solver | 28.31 | 39.78 | 20.00 | 100.00 |
| Solver — risk off | solver | 29.08 | 41.07 | 20.00 | 100.00 |
| Baseline — capability x salience weighted mean | baseline | 23.64 | 30.31 | 18.46 | 93.20 |
| Baseline — median actor position | baseline | 28.37 | 40.64 | 20.00 | 100.00 |
| R=dynamic, Q=1 | sweep | 28.31 | 39.78 | 20.00 | 100.00 |
| R=dynamic, Q=0.5 | sweep | 28.53 | 39.65 | 21.77 | 100.00 |
| R=fixed, Q=1 | sweep | 28.36 | 39.86 | 20.00 | 100.00 |
| R=fixed, Q=0.5 | sweep | 28.67 | 40.03 | 20.00 | 100.00 |

★ = the primary config the gate is judged on. Lower is better; scale is 0-100.

## Worst issues (by the primary solver's absolute error)

| Issue | Proposal | Forecast | Actual | Error |
|---|---|---:|---:|---:|
| d04209i2 | worktime | 100.0 | 0.0 | 100.0 |
| d05246i4 | custom | 0.0 | 100.0 | 100.0 |
| d05281i4 | waste | 0.0 | 100.0 | 100.0 |
| d98195i2 | socrates | 0.0 | 100.0 | 100.0 |
| d98195i3 | socrates | 100.0 | 0.0 | 100.0 |
| d98300i2 | Turkey | 0.0 | 100.0 | 100.0 |
| n00030i4 | visas | 0.0 | 100.0 | 100.0 |
| n00250i2 | CMOsugar | 100.0 | 0.0 | 100.0 |
| n00250i3 | CMOsugar | 100.0 | 0.0 | 100.0 |
| n05124i2 | rightsag | 100.0 | 0.0 | 100.0 |

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

- **Capability.** DEU records position and salience but no capability, so every actor is assigned a fixed capability of 100 (D9.2). With equal capability the weighted-mean baseline is the salience-weighted mean — a classic DEU 'compromise' model.
- **Point estimates.** Each issue is point estimates, so Monte Carlo is degenerate (zero variance, D3.1); the harness solves each issue once deterministically. `--draws` (2000) is recorded for interface parity but does not affect the result (D9.3).
- **Determinism.** Dataset pinned by SHA-256 `0d75f0d2f3a96982…`; engine `2b9c82b6b261`; seed 42. Same inputs → byte-identical record.

