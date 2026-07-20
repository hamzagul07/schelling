# DECISIONS.md

Every interpretive choice made against the source papers in `docs/papers/`, with the
equation number and page it came from. Divergences are explained, never hidden
(CLAUDE.md rule 3). Newest session last.

Sources:
- **Scholz** = Scholz, Calbert & Smith (2011), *Unravelling Bueno De Mesquita's Group
  Decision Model*, `docs/papers/scholz_2011_unravelling_bdm.pdf`.
- **Feder** = Feder (1987), *FACTIONS and Policon*, `docs/papers/feder_1987_factions_policon.pdf`.

---

## Session 1 — schemas + vote layer (BUILD_PLAN §3, §4 steps 1-3)

### D1.1 — Vote formula: folded constants (Scholz eq. 26, 28, 29)
Scholz eq. 26 defines the votes actor *i* casts comparing positions `x_j`, `x_k` as
`v_i^{jk} = c_i s_i (u^i x_j − u^i x_k)`. Expanding the utility with eq. 14
(`u^i x_k = 1 − 2|x_i − x_k| / (x_max − x_min)`) gives eq. 28:
`v_i^{jk} = 2 c_i s_i (|x_i − x_k| − |x_i − x_j|) / (x_max − x_min)`, summed over actors in
eq. 29.

BUILD_PLAN §4.2 states the form as `w_i (|x_i − x_k| − |x_i − x_j|) / R` with
`w_i = c_i s_i / 100` (§4.1). We implement §4.2 verbatim: we fold `c_i s_i` into `w_i`
(with the Policon `/100` normalization) and drop the constant factor `2`.

**Why this is exact, not an approximation:** the winner of a contest depends only on the
*sign* of the summed votes, which a positive constant multiplier cannot change. Every
downstream consumer of vote *magnitude* — notably the alliance/challenge probability
`P^i` (Scholz eq. 30-31) — is a ratio of vote sums in which the constant `2` and the
`/100` cancel identically. So no result the engine reports is affected. Recorded here so a
reader comparing our code to eq. 28 is not surprised by the missing `2`.

### D1.2 — Continuum range `R` is an explicit parameter, not `max(x) − min(x)`
Scholz uses `x_max − x_min` = the range of *positions*. We instead pass the continuum
range `R` explicitly to the vote functions and set it to the full policy scale (100 for the
0-100 Policon scale). Rationale: `R` is a fixed property of the *issue continuum*, defined
once in `GameSpec.continuum`, and must not shift round-to-round as actors converge and the
spread of positions shrinks (which `max − min` would). Because `R` divides every term
uniformly it never changes a contest winner or the weighted median; it only sets the units
of the (otherwise unused-in-Session-1) vote magnitudes. Revisit if the replication
(Session 2) shows the paper intends the shrinking `max − min`.

### D1.3 — Weighted median via cumulative weight; lower-median tie rule
BUILD_PLAN §4.3 defines the headline forecast as "the position that defeats every
alternative in pairwise contests" — the Condorcet winner. Black's median-voter theorem
(cited by Scholz §3.2) guarantees that for these single-peaked, distance-based preferences
the Condorcet winner is exactly the classic weighted median. We therefore compute it
directly from cumulative weight (O(n log n)) rather than by scanning the full contest
matrix, and assert the two agree in `test_votes.py`. When cumulative weight reaches exactly
half the total at a position, we take that (lower) position — the standard *lower* weighted
median — so the forecast is a deterministic function of inputs (CLAUDE.md rule 2).

### D1.4 — Solver consumes the `mode` of each triangular estimate
The deterministic solver reads `position.mode`, `salience.mode`, `capability.mode`
(`game_mode_arrays`). The low/high tails exist only for Monte Carlo sampling (§6). A point
estimate (`low == mode == high`), as in the replication fixture, makes this a no-op.

### D1.5 — `SolverResult` / `ForecastRecord` fields deferred to later milestones
BUILD_PLAN §3 describes these schemas in prose (not fixed JSON). We fixed the field *shapes*
now (`RoundLog.octant_matrix`, `offers`; `ForecastRecord.outcome_distribution`, `ci80`,
`sensitivity`, `convergence_stats`) but leave them defaulted/empty in Session 1, since they
are produced by the round loop (§4 steps 4-8, Session 2) and the Monte Carlo layer (§6,
Session 3). Names freeze once `test_replication.py` is green, per §3.

---

## Session 2 — the model + the replication gate (BUILD_PLAN §4 steps 4-8, §5)

Equation numbers refer to `docs/papers/scholz_extract.md`. Ambiguity labels (A1-A4) are
defined there. The BDM-1994 emission-standards replication is the arbiter of every choice
below (BUILD_PLAN §4: "implement the interpretation that reproduces their replication").

### D2.1 — Leading salience in the challenge EU is the *responder's* (A1)
Scholz eq. 6 writes `E^i(U_ij)_c = s_j(...) + (1 - s_j) U_si`, so the salience weighting the
active-response branch is the *responder's* (`s_j` when i challenges j). By the i↔j swap,
`E^j(U_ji)` uses `s_i`. `expected_utility()` normalizes the responder's 0-100 salience to
[0,1] (`s_resp = salience[responder]/100`) — the term `(1 - s_resp)` requires a probability,
which the raw 0-100 value is not. Capability never enters the EU directly (only via `P`, a
ratio), so its scale is irrelevant. *Confidence: high.*

### D2.2 — Continuum range `R`: dynamic is the replication default (resolves D1.2)
Per the Session-1 review, `R` is now a `SolverConfig` option (`RangeMode`): `DYNAMIC`
(`max - min` of the current round's positions, Scholz's literal reading) or `FIXED` (a set
value, default 100). The BDM-1994 table uses positions in **years (4-10)**, so `FIXED=100`
is meaningless there; the paper's normalized distances `|x_i - x_j|/(x_max - x_min)` imply
`DYNAMIC`. **`DYNAMIC` is therefore the default and the replication uses it.** `FIXED` remains
our documented upgrade for inputs already on a 0-100 continuum (the toy fixture, future live
cases). `R` divides every utility term uniformly, so it never changes a contest winner or the
median — only the curvature of the utility surface.

### D2.3 — Security level = adversaries' challenge EU (column sum) (A2)
Scholz §5 (p. 24) defines security as "the utility i believes its adversaries expect to
derive from challenging i" = `Sec_i = Σ_{j≠i} E^j(U_ji)` = column `i` of the EU matrix
(`security_mode="adversary"`, the default). The Appendix step-8 formula prints `E^i(U_ji)`
(a responder-EU reading), which we expose as `security_mode="own"` (row sum) but do not use —
the prose definition is unambiguous and reproduces the replication. *Confidence: medium.*

### D2.4 — `T` operationalized as "median closer to i than j is"
The no-challenge better/worse selector `T` (eqs. 20-23, figs. 1-4) is set to `1` iff
`|x_i - μ| < |x_i - x_j|`, which reproduces all four of Scholz's cases (1 & 3A → T=1; 2 & 3B
→ T=0). Moot for the replication: with `Q = 1.0` the entire `(1-Q)(T U_b + (1-T) U_w)` term
vanishes, so `U_b`, `U_w` and `T` do not affect the BDM-1994 result. *Confidence: high (and
untested by the replication — flagged for Session 3+ when `Q < 1` cases appear).*

### D2.5 — Offer selection: most-enforceable first, least-move as tie-break (A4)
Scholz §6.2 (p. 251): "those better able to enforce their wishes… make their proposals stick;
given equally enforceable proposals, players move the least." We implement exactly that
order: each mover accepts the offer from the proposer with the highest expected utility
(`Offer.enforceability` = the winning actor's EU); ties in enforceability break to the
smallest `|Δx|`, then to the smaller target position for determinism. An earlier
least-movement-first reading pulled mid-actors *downward* (tie-broken to the smaller
position) and made the median fall — clearly wrong, and corrected by reading enforceability
as primary. *Confidence: medium — the primary replication lever.*

### D2.6 — Conflict is an "uncertain outcome" → no deterministic move (A4, key choice)
BDM (1997, p. 244): when both actors expect to gain (`E^i(U_ij) > 0` **and** `E^j(U_ji) > 0`)
"conflict is likely and that conflict has an uncertain outcome." We read this literally:
conflict produces **no deterministic position change** (`conflict_resolves=False`, the
default). Only compromise (partial move, eqs. 35-36) and compel (full move) shift positions.
This is decisive: treating conflict as a full move (the BDM-1984 confrontation-octant reading)
makes *every* actor stampede to position 10 (mean → 10), whereas the no-move reading preserves
the spread Scholz report (mean stays ≈ 7.5) and lands the median in the right band. Both
readings are available via the config flag. *Confidence: medium-high — validated by the
replication's mean/spread, not just its median.*

### D2.7 — Replication result and residual deviation (BUILD_PLAN §5)
With the paper-faithful config (`DYNAMIC` R, `Q=1.0`, risk on, adversary security, conflict =
no move) the solver converges (stopping rule fired, 3 rounds) to:

| statistic        | ours   | Scholz Table 2 (steady) | BDM stabilised | within ±1.0? |
|------------------|--------|-------------------------|----------------|--------------|
| median forecast  | 9.53   | 9.9 (rounds 2-5)        | 9.05           | yes (0.37 / 0.48) |
| mean, round 1    | 7.61   | 7.4                     | —              | yes (0.21)   |
| mean, round 2    | 7.72   | 7.5                     | —              | yes (0.22)   |

**The gate passes**: the converged median forecast is within ±1.0 of both the Scholz-reproduced
steady-state (9.9) and BDM's own stabilised prediction (9.05), and the early-round means match
Scholz's ≈7.4-7.6 band with the position spread preserved.

**Residual deviation (quantified, not hidden):** we do *not* bit-reproduce Scholz's exact
per-round median trajectory `8.4, 9.9, 9.9, 9.9, 9.9`. Our median jumps from the initial 7.0
to ~9.5 in round 1 and holds, rather than stepping through 8.4 then 9.9. Hypothesis: the
round-1 value 8.4 depends on the precise figure-6 octant boundaries for
Compel/Capitulate/Stalemate and the exact offer-selection tie-handling — all figure-only in
the paper, none given as inequalities — plus Scholz's own note (p. 28) that their trajectory
"does not stabilise" and continues to wander (their rounds 6-8 read 7.4, 8.8, 9.6). The steady
value and the mean/spread, which are the substantive forecast, match. Closing the last
transient would require Scholz's unpublished code; per BUILD_PLAN §5 this analysis is logged
rather than papered over by loosening the ±1.0 tolerance.

### D2.8 — D1.1 guard verified: no non-ratiometric use of vote magnitude
Confirmed while implementing EU (Session-1 review action 3a): vote quantities enter the model
only (i) as the argmax that selects the median `μ` (sign/order — scale-free) and (ii) as the
prevail probability `P^i` (Scholz eq. 31), which is a *ratio* of `c_k s_k`-weighted sums in
which any common factor cancels. No formula uses a raw vote magnitude, so folding the constant
`2` and the `/100` into the weights (D1.1) changes nothing. The Session-1 constants stand.

### D2.9 — Compromise j-upper-hand sign follows the figure, not the text (A3)
Scholz's Compromise text prints the j-upper-hand clause as `E^j(U_ji) < 0`, contradicting
figure 6 (Compromise− sits at `E^j(U_ji) > 0`). We follow the figure and symmetry: i has the
upper hand at `(a>0, b<0, |a|>|b|)`, j at `(a<0, b>0, |b|>|a|)`. *Confidence: high.*

---

## Session 3 — Monte Carlo + sensitivity (BUILD_PLAN §6)

### D3.1 — Triangular draws; point estimates pass through with zero variance
`sample_triangular` draws from `numpy`'s triangular `(low, mode, high)`. numpy requires
`left < right`, so a degenerate point estimate (`low == high`) short-circuits to the mode
unchanged. Consequently the replication fixture (all point estimates) is a valid MC input:
every draw is identical, giving an exact zero-variance distribution equal to the Session-2
forecast — the basis of the zero-variance test.

### D3.2 — Per-draw RNG derived via `SeedSequence(master, spawn_key=(draw,))`
Each draw's generator is `np.random.default_rng(SeedSequence(entropy=master_seed,
spawn_key=(draw_index,)))`. `SeedSequence` gives well-separated, independent streams per draw
while keeping the whole ensemble reproducible from the master seed alone — same master seed →
byte-identical `ForecastRecord` (CLAUDE.md rule 2). Preferred over `default_rng(master + i)`,
whose adjacent seeds can correlate.

### D3.3 — MC record aggregation semantics (repurposing the two scalar forecast fields)
`ForecastRecord.outcome_distribution` is the sorted distribution of each draw's converged
headline **median**. From it: `forecast_median` = its median (central estimate),
`forecast_mean` = `settlement_point` = its mean (expected outcome), `ci80` = (p10, p90). The
Session-2 `SolverResult` used `forecast_median`/`forecast_mean` for two statistics of one
deterministic run; at the MC layer they become two summaries (median, mean) of the *median*
distribution. `MonteCarloResult` also retains the per-draw weighted-mean distribution for
future use, but the record's headline is the median distribution — the model's stated
forecast quantity.

### D3.4 — `inputs_hash` covers game **and** config; `run_id` and timestamps are deterministic
Per the Session-3 brief, the solver config (R mode, Q, security mode, conflict rule, …) is
part of the run inputs, so `inputs_hash` = SHA-256 of canonical
`{game, config}` JSON (sorted keys). `run_id` is derived as
`{question_id}-mc{n}-s{seed}-{hash[:12]}`, so identical inputs address the same record file.
`engine_version` is the git commit SHA (deterministic within a commit; `"unknown"` outside a
repo). `created_at` defaults to `None` and is the only non-deterministic field a caller may
set — kept out of `inputs_hash` and defaulted off so two runs are byte-identical, honoring
CLAUDE.md rule 2 ("no wall-clock timestamps inside hashed content").

### D3.5 — Vectorized `eu_matrix`, bit-exact with the scalar version
The per-dyad Python loop made 10k draws ~79 s (over the §6 60 s budget). `eu_matrix` is now
fully numpy-broadcast (an `n×n×n` `arg` tensor for the prevail probability, `n×n` utility
arrays). It is **bit-exact** against the scalar `expected_utility` (parity test, `abs=1e-12`,
observed error 0.0), so no solver result changed — the Session-2 replication median is still
9.53. 10k draws now run in ~4 s. A defensive `np.maximum(base, 0.0)` guards the fractional
powers against float-noise negatives (a no-op where distances are ≤ R, as they always are).

### D3.6 — Schema refinement of the Session-1 placeholder fields (names preserved)
Implementing §6 enriched the deliberately-loose §3 placeholders (D1.5): `sensitivity` is now
`list[SensitivityEntry]` (structured rows) rather than `list[dict[str, float]]`, and
`ForecastRecord` gains `n_draws` and `solver_config`; `created_at` became `str | None`. Field
*names* are unchanged and the replication stays green, so the "freeze once replication passes"
rule is respected — only the provisional shapes were filled in at the point of implementation.
