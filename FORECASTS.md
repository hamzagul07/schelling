# FORECASTS.md — the sealed forecast ledger

Pre-registered predictions on real, unresolved events, sealed before the outcome is known and
graded afterward. Each question is forecast by **both** models — the challenge (BDM bargaining)
solver and the compromise (capability x salience weighted mean) model — so the DEU-backtest verdict
(the compromise model wins) is put to a live, out-of-sample test. Inputs are frozen and their hash
is recorded; the sealed game files themselves stay out of the public tree.

## Q-2026-USIRAN-STAGE2

- **Frozen:** 2026-07-21  ·  **Grade on:** 2026-09-01
- **Continuum:** Shape of a comprehensive US-Iran settlement (0=maximal US/Israel, 100=maximal Iran)
- **Note:** Will US-Iran advance to MOU stage two by 31 Aug 2026? (0=US/Israel maximal, 100=Iran maximal)

| Model | Forecast (median) | CI80 | inputs_hash | commitment |
|---|---:|---|---|---|
| challenge | 34.576 | [24.89, 56.19] | `2cbb0bc624f3` | `513722cd5d89e1ff` |
| compromise | 41.636 | [39.06, 44.30] | `2cbb0bc624f3` | `13d11683f1f29a3e` |

The commitment hash seals each forecast independent of engine version; re-running the sealed game with the same seed reproduces it. The outcome will be scored as |forecast - actual| on the same 0-100 continuum.
