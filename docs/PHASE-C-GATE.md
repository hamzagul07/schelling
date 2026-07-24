# Phase C solver gate — pre-registration (Session 41)

**Pre-registered 2026-07-24, committed before any Phase C solver code is written and before any DEU
run.** This file fixes, in advance, the rule by which the new solvers earn a place on the living
leaderboard — so the verdict cannot be reverse-fit to the result. It mirrors exactly how the
`gravity` and `regime` successor candidates were pre-registered and scored (DECISIONS.md R1, Session
R1) and how the negative result was reported honestly (`BACKTEST.md`).

## The solvers under test

Four new deterministic solver options, each registered under the D39 engine as a new `--solver`
value. **No existing solver's numerical path changes, and the D39.2 regression gate must pass
untouched.** All four are **parameter-free structural game-theoretic models** — none is fitted to
DEU, so there is no train/dev tuning stage to protect; the held-out TEST split is scored **once**.

| `--solver` | Method | Free parameters |
|---|---|---|
| `challenge-qre` | Quantal-response softening of the challenge model's offer acceptance | λ = 1.0, **fixed a priori** (see below), not fitted |
| `nash` | Weighted Nash bargaining over actor utilities; reference point = disagreement point | none |
| `nash-ks` | Kalai-Smorodinsky bargaining (second variant) | none |
| `pce` | KTAB-style probabilistic Condorcet election | none |

**The one free parameter, disclosed and fixed in advance:** `challenge-qre` uses a logit rationality
parameter **λ = 1.0**, applied to the offer-enforceability differences (expected utilities on the
Scholz utility scale, roughly [−4, 4]). It is a deliberate "moderately rational" a-priori choice, is
**not** tuned on DEU or any other data, and is disclosed here before any run. λ → ∞ would recover the
existing deterministic challenge model exactly; a finite λ makes offer acceptance soft. The point of
the QRE run is the diagnostic: **does the degenerate median lock (D12.3) disappear** when choices are
softened? That is reported honestly whatever the answer.

## The gate

Each solver is scored on the **pre-committed DEU III held-out TEST split** (`deu3_split.json`, split
seed 20260721: 106 TEST issues, 79 with a reference point; committed before any fitting), with
**sourced capability** (treaty-regime Council power, D10.1), exactly as the successor candidates were.
`nash` / `nash-ks` are scored on the TEST rp-issues (they need a disagreement point); `challenge-qre`
and `pce` are scored on all TEST issues.

A solver enters the leaderboard as a **VALIDATED** method only if it **beats the compromise
capability×salience weighted mean** on the TEST split:

> **delta = MAE(solver) − MAE(compromise) < 0 on TEST, AND the 95% paired-bootstrap confidence
> interval of that delta (seed 20260721, 2000 resamples) lies entirely below 0** (i.e. does not
> straddle zero).

This is the same two-part rule the successor candidates faced: a point improvement that is also
statistically distinguishable from zero. A solver that does not clear both bars ships as an
**EXPLORATORY** `--solver` option, clearly labelled on the leaderboard, exactly as `gravity` and
`regime` did — available for inspection, never sealed against a live forecast.

**Nothing is sealed against a live question unless it survives this gate.** The compromise mean
remains the settlement model for DEU unless and until a solver beats it here.

## A-priori expectation (stated so it cannot be claimed after the fact)

The oracle diagnostic (D11.0) put a flexible cross-validated model at MAE 23.84 against the
compromise mean's 22.99 — i.e. **the mean is already at the extractable-signal ceiling** on DEU.
Sessions 9, 10 and R1 all failed to beat it for that reason. A parameter-free structural solver is
therefore *a priori unlikely* to clear the gate; the honest expected outcome is that all four ship
exploratory. We pre-register and run anyway, because a negative result under a fixed rule is itself
evidence, and because the QRE median-lock diagnostic is worth having regardless of the MAE verdict.

## Reporting

Results are written to the living leaderboard in `BACKTEST.md` (between the idempotent LEADERBOARD
markers) alongside `gravity` and `regime`, with the TEST MAE, the compromise MAE, the delta and its
95% CI, and the verdict. The verdict is reported exactly as computed — no solver is relabelled after
seeing its number.
