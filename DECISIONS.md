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
