# OUTLINE.md — paper skeleton (stubs only; NO prose)

> Bullet-level content only. Every empirical claim points to an `EVIDENCE.md` row (E-tags) or a
> `figures/` asset. Guardrail: coercive verdict stays PENDING; ceiling claim stays scoped; no
> number appears here that is not sourced in EVIDENCE.md.

## Title candidates
- **FINAL (D15.3):** "Structure, Not Magic: An Open Replication and Predictability Ceiling for the Bueno de Mesquita Forecasting Model" — set as the manuscript H1 in `00-abstract.md`.
- ~~"The LLM Structures, the Math Predicts: An Open, Deterministic Rebuild of the Bueno de Mesquita Group-Decision Model"~~
- ~~"Unbundling Policon: A Reproducible Expected-Utility Forecaster and Why a Weighted Mean Still Wins"~~
- ~~"Structure, Not Magic: Reinterpreting Expert-Elicitation Forecasting with a Fully Auditable BDM Engine"~~
- ~~"A Commit-Reveal Forecasting Engine: Replication, a Fair Fight, and a Suppressed Verdict"~~

## 1. Introduction & the Policon / BDM lineage
- Problem: BDM/Policon forecasts are cited but not independently reproducible; equations behind paywalls/proprietary tools
- Lineage stub: Bueno de Mesquita expected-utility group model → Policon → KTAB/SMP; Scholz–Calbert–Smith (2011) as the open re-derivation we build from [cite docs/papers/scholz_2011]
- Thesis: separate structuring (LLM: extract stakeholder tables, classify templates) from prediction (deterministic solver + Monte Carlo) — CLAUDE.md rule 1
- Contribution bullets: (a) open Scholz-faithful solver; (b) determinism/auditability as first-class; (c) DEU fair-fight negative result; (d) pre-registered successor search; (e) noise-floor ceiling; (f) elicitation reinterpretation; (g) blind dual-entry case library; (h) commit-reveal ledger
- Non-contribution / scope guard: no new coercive verdict claimed (see §7); ceiling claim is domain-scoped (see §5)

## 2. The open replication (Scholz-faithful method, DECISIONS discipline, the 9.53 gate)
- Method stub: equations transcribed from papers not memory (CLAUDE.md rule 3); every interpretive choice logged in DECISIONS.md with equation number + page
- Determinism stub: explicit seed; same seed+inputs → byte-identical ForecastRecord (rule 2)
- Replication gate: emission-standards case reproduces the published settlement → [E-REPL-MEDIAN], within tolerance of 9.5x; zero-variance point fixture → CI collapses [E-REPL-CI]
- Artifact: tests/fixtures/emission_standards.json; deterministic ForecastRecord
- Figure: none (single point)

## 3. The fair fight (real Council capabilities, reference point)
- Setup stub: DEU III benchmark, N issues [E-DEU-N]; point-estimate games solved once deterministically (MC degenerate)
- Fairness stub: sourced treaty-regime Council power (pre-Nice / Nice / Lisbon) feeds challenge solver AND weighted-mean baseline equally (D10.1); reference-point-anchored challenge, Q tuned split-sample (D10.4)
- Gate v2 (fixed in advance): fully-equipped challenge must beat the equally-equipped weighted mean → FAILED [E-DEU-GATE], [E-METHOD-challenge_rp], [E-METHOD-baseline_wmean], [E-METHOD-baseline_median]
- Split-sample honesty: train/test halves; tuned Q; held-out test MAE still loses [E-SS-TEST]
- Per-method table → figures/fig_challenge_vs_compromise.svg + [E-METHOD-*]
- Published-context stub: same regime/ordering as BdM (2011) Old Model vs weighted mean [E-CTX-*]; NOT like-for-like (different DEU version/subset)

## 4. The pre-registered successor search (git-commit-as-preregistration; both candidates fail held-out)
- Pre-registration mechanism stub: 40/30/30 split committed BEFORE any candidate code — git history is the audit trail (commit order) [E-R1-SPLIT]
- Candidates: A = status-quo gravity (λ·wmean+(1−λ)·rp); B = regime-aware softmax blend
- Protocol: fit on train, tune on dev, score TEST once; paired bootstrap 95% CI [E-R1-gravity], [E-R1-regime]
- Result: neither beats the compromise mean on TEST; both CIs straddle 0 → indistinguishable, not better; nothing sealed
- B collapses onto compromise (learned regime weight) — rediscovers the weighted mean
- Figures: figures/fig_r1_split.svg; figures/fig_leaderboard.svg

## 5. The noise-floor oracle and the ceiling claim (SCOPED)
- Oracle stub: deliberately flexible CV model (ridge + rich features incl. positions), 5-fold, seeded → oracle MAE [E-ORACLE-MAE]
- Ceiling claim: gap = compromise − oracle ≈ [E-ORACLE-GAP]; the flexible model does not beat the mean → mean is at/near the extractable-signal ceiling
- SCOPE GUARD (explicit): claim holds for COOPERATIVE EU-legislative bargaining on the CLASSIC input set (positions/salience/capability); NOT a universal ceiling; says nothing about coercive settings (§7) or richer feature sets
- Implication: explains why §3 and §4 all fail — there is little signal beyond the influence-weighted average here

## 6. The elicitation reinterpretation (Feder's "analysts beaten" without magic)
- Puzzle stub: Feder (1987) reports the model beat CIA analysts [cite docs/papers/feder_1987]
- Reinterpretation stub: the win is structuring, not a superior world-model — the model aggregates elicited positions/salience/capability consistently; no probability is produced by any elicitation step
- Consistency-with-§5 stub: if the mean is at the ceiling, the model's value is disciplined aggregation of expert inputs, not extra predictive signal — dissolves the "magic"
- No new numeric claim; interpretive section anchored to §5 result

## 7. The case-library protocol (blind dual entry) and the PENDING coercive verdict
- Protocol stub: blind dual machine transcription + human ratification of judgments (D13.0); Exercised Power = Influence×Salience/100 as per-row checksum; capability ← Influence mapping
- China case stub: Efird–Lester–Wise (2016) Tables 2–3 verified 60/60 rows across two blind reads [E-CHINA-ROWS]; judgments (outcome codings, horizon) ratified by human; verified flag gated on ratification [E-CHINA-VERIFIED]
- Horizon finding stub: paper states no calendar horizon (10 "turns" = bargaining rounds); horizons are our scoring convention
- Japan case stub: BLOCKED pending KAPSARC KS-2018-DP47 PDF; scaffold records differing column order + checksum
- COERCIVE VERDICT: **PENDING** — expert-coded coercive classics (Hong Kong 1985, Iran 1984) paywalled; harness built, waits on printed inputs (D11.1); domestic-bargaining cases are out-of-domain and never counted toward a coercive verdict [E-DOMAIN-VERDICT]

## 8. The commit-reveal ledger as live methodology
- Mechanism stub: seal a forecast by SHA-256 of its runs/ record BEFORE resolution; records gitignored so no number editable post-hoc (D12.0/D12.1)
- Live pre-registrations: US-Iran stage-two, 2 vintages × 2 model families, sealed [E-LEDGER-*]; resolution 2026-08-31 / grading 2026-09-01
- Out-of-sample test stub: a live test of the DEU verdict (does compromise beat challenge out-of-domain too?) — decided at grading, not by us now

## 9. Limitations
- DEU outcome-coding coarseness: 0/100 poles dominate worst errors; ordinal→continuum mapping is lossy [E-WORST-*]
- Capability-table construction choices: treaty-regime power rescaled; Commission/EP = largest member (D10.3) — a defensible but contestable modeling choice
- Single-domain empirics: only cooperative EU-legislative bargaining is benchmarked; coercive column PENDING (§7)
- Small-N case library: N is tiny; no verdict claimed under the harness's own guards
- Elicitation dependence: garbage-in/garbage-out on expert inputs; no live-search facts enter backtests (rule 7)

## 10. Conclusion
- Restate: structuring/predicting split delivers reproducibility; the honest result is a negative one on DEU
- The ceiling reframes "which model wins" as "how much signal exists" — scoped to this domain
- Open threads: coercive verdict (PENDING), the sealed US-Iran grading, a larger verified case library
- Reproducibility statement: every number regenerable via `schelling paper-evidence`; figures via the same command; determinism seeds fixed
