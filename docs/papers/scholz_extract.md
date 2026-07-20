# Scholz et al. (2011) — equation extract (§3–4, plus Appendix algorithm)

Source: `scholz_2011_unravelling_bdm.pdf`, *Unravelling Bueno De Mesquita's Group Decision
Model*, ICAART 2011, pp. 18–30. Extracted equation-by-equation for the Session-2 solver.
Paper section numbers (§) and equation numbers (eq.) are the paper's own. Page numbers are
the printed journal pages (18–30).

**Notation.** `x_i` = actor *i*'s position; `c_i` = capability; `s_i` = salience;
`R = x_max − x_min` = continuum range; `μ` = median-voter position; `r_i` = risk exponent
(lower-case); `R_i` = risk basis in [−1, 1] (upper-case); `Q` = status-quo probability;
`T` ∈ {0,1}. For an ordered dyad, `U_ij` denotes "i challenges j"; the superscript on `E`
denotes whose expected utility. `U_si, U_fi, U_bi, U_wi, U_sq` = success / failure / better /
worse / status-quo basic utilities.

---

## The complete algorithm (Appendix, pp. 29–30) — the spine

1. Given actors i=1..n, initial positions `x_i(t=0)`, `c_i`, `s_i`, and number of rounds τ.
2. Let `r_i = 1`.
3. Pairwise votes (eq. as printed in Appendix step 3):
   `v^{jk} = Σ_i c_i s_i ( (|x_i − x_k| − |x_i − x_j|) / (x_max − x_min) )`.
   Then find the maximum value which corresponds to the Condorcet-winner position = median `μ`.
4. Basic utilities (Appendix step 4):
   - `U_si^i = 2 − 4 [ 0.5 − 0.5 · |x_i − x_j| / R ]^{r_i}`            (eq. 15)
   - `U_fi^i = 2 − 4 [ 0.5 + 0.5 · |x_i − x_j| / R ]^{r_i}`            (eq. 16)
   - `U_bi^i = 2 − 4 [ 0.5 − 0.25 · (|x_i − μ| + |x_i − x_j|) / R ]^{r_i}`  (eq. 22)
   - `U_wi^i = 2 − 4 [ 0.5 + 0.25 · (|x_i − μ| + |x_i − x_j|) / R ]^{r_i}`  (eq. 23)
   - `U_sq^i = 2 − 4 (0.5)^{r_i}`                                     (eq. 24)
5. Probabilities (Appendix step 5 = eq. 30/31):
   `P^i = [ Σ_{k : arg>0} c_k s_k (|x_k − x_j| − |x_k − x_i|) ] / [ Σ_{k=1}^n c_k s_k · | |x_k − x_j| − |x_k − x_i| | ]`
   where `arg = |x_k − x_j| − |x_k − x_i|` (>0 ⇒ k is closer to i than to j, i.e. supports i).
   Note `P^j = 1 − P^i` (numerators of i- and j-supporters partition the denominator).
6. Let `Q = 0.5` (or `1.0`). — **For the BDM-1994 replication Scholz chose `Q = 1.0`** (p. 27:
   "No value for Q was given. We chose Q=1.0.").
7. Expected utilities (Appendix step 7 = eqs. 5–7, 25a/25b):
   `E^i(U_ij) = s_j (P^i U_si^i + (1−P^i) U_fi^i) + (1−s_j) U_si^i − Q U_sq^i − (1−Q)(T U_bi^i + (1−T) U_wi^i)`
   `E^j(U_ji) = s_i (P^j U_sj^j + (1−P^j) U_fj^j) + (1−s_i) U_sj^j − Q U_sq^j − (1−Q)(T U_bj^j + (1−T) U_wj^j)`
   (Leading salience is the **responder's**: `s_j` in `E^i(U_ij)`, `s_i` in `E^j(U_ji)` — from
   eq. 6 and its i↔j swap. See ambiguity A1.)
   If this is the second pass (r_i already recomputed) go to step 11.
8. Risk basis (eq. 32, restated precisely as eq. 34):
   `R_i = [ 2·Sec_i − max_k Sec_k − min_k Sec_k ] / [ max_k Sec_k − min_k Sec_k ]`,
   where `Sec_i = Σ_{j≠i} E^i(U_ji)` is i's security level (§5, p. 24). Maps to [−1, 1].
   (Superscript on the security term is ambiguous — see A2.)
9. Risk exponent (eq. 33): `r_i = (1 − R_i/3) / (1 + R_i/3)`. Maps `R_i∈[−1,1]` → `r_i∈[0.5, 2]`
   (R_i=−1 ⇒ r_i=2, most risk-acceptant; R_i=+1 ⇒ r_i=0.5, most risk-averse).
10. Go to step 4, using the calculated `r_i` (second pass).
11. Determine new positions `x` from the octant of `(E^i(U_ij), E^j(U_ji))` per §6 (see below).
12. Increment round, `t = t+1`.
13. If `t = τ` stop.

Risk-averaging note (§5, pp. 24): "first determine the expected utilities using r_i=1, then
apply (34) and (33) to estimate r_i, and lastly re-apply the r_i estimates to re-estimate the
expected utilities." So the EU used for the octant/position step is the **second-pass**
(risk-adjusted) EU; the security sum in step 8 uses the **first-pass** (r_i=1) EU.

---

## §3 Utilities — full forms (pp. 20–23)

- eq. 5:  `E^i(U_ij) = E^i(U_ij)_c − E^i(U_ij)_nc`
- eq. 6:  `E^i(U_ij)_c = s_j (P^i U_si^i + (1−P^i) U_fi^i) + (1−s_j) U_si^i`
- eq. 7:  `E^i(U_ij)_nc = Q U_sq^i + (1−Q)(T U_bi^i + (1−T) U_wi^i)`
- eq. 9:  `u^i x_k = f(−|x_k − x_i|)` — utility is a decreasing function of distance.
- eq. 14: `U_ij^i = U_ji^i = 1 − 2 |x_i − x_j| / R`  (and `U_ii^i = U_jj^i = 1`, eq. 13).
- eq. 15: `U_si^i = 2 − 4 [ 0.5 − 0.5 |x_i − x_j| / R ]^{r_i}`  (success utility)
- eq. 16: `U_fi^i = 2 − 4 [ 0.5 + 0.5 |x_i − x_j| / R ]^{r_i}`  (failure utility)
- eq. 22: `U_bi^i = 2 − 4 [ 0.5 − 0.25 (|x_i − μ| + |x_i − x_j|) / R ]^{r_i}`  (better, no-challenge)
- eq. 23: `U_wi^i = 2 − 4 [ 0.5 + 0.25 (|x_i − μ| + |x_i − x_j|) / R ]^{r_i}`  (worse, no-challenge)
- eq. 24: `U_sq^i = 2 − 4 (0.5)^{r_i}`  (status quo)

`T` (eqs. 20–23 derivation, figures 1–4, p. 22): for the no-challenge branch, j is expected
to move to the median μ. Four cases:
- Case 1 (μ between i and j): j's move improves i ⇒ `T = 1`.
- Case 2 (j between i and μ): j's move worsens i ⇒ `T = 0`.
- Case 3A (i between j and μ, improves): `T = 1`.
- Case 3B (i between j and μ, worsens): `T = 0`.
"cases 1 and 3A correspond to T=1 and cases 2 and 3B correspond to T=0" (p. 22).
Operationalized here as: **`T = 1` iff `|x_i − μ| < |x_i − x_j|`** (median closer to i than j
is), else `T = 0`. This reproduces all four cases. (With `Q = 1.0` the whole `(1−Q)(…)` term
vanishes, so T is irrelevant to the BDM-1994 replication.)

## §4 Alliance probability (p. 24)

- eq. 30: `P^i = ( Σ_{k : u^k x_i > u^k x_j} v_k^{ij} ) / ( Σ_{k=1}^n |v_k^{ij}| )`
- eq. 31: expanded form = Appendix step 5 above.

## §5 Risk propensity (p. 24)

- Security: `Sec_i = Σ_{j≠i} E(U_ji)` (p. 24). Scholz use the **BDM-1985** conversion (eq. 32/34),
  explicitly rejecting BDM-1997's reversed, range-breaking subscripts.
- eq. 32/34: `R_i` as in Appendix step 8.
- eq. 33: `r_i = (1 − R_i/3)/(1 + R_i/3)`.

## §6 Decision — octants & offers (fig. 6, p. 25)

Classify each ordered dyad by `(a, b) = (E^i(U_ij), E^j(U_ji))`. Axes: `a` horizontal, `b`
vertical ("Others"). Text-precise regions:

- **Conflict** (BDM 1997, p. 244): `a > 0 and b > 0`. Both believe they win; outcome uncertain.
  Split by the `a = b` diagonal into two confrontation octants (BDM 1984 labels, p. 230,
  "Challenger Favored" / "Favoring Focal Group"), interpreted (p. 25) as:
  - Confrontation− (`b > a`): **i moves to j** (full move to `x_j`).
  - Confrontation+ (`a > b`): **j moves to i** (full move to `x_i`).
  (i.e. the lower-EU actor concedes fully to the higher-EU actor.)
- **Compromise** (p. 25): opposite-sign EUs; the actor with the larger |EU| has the upper hand.
  - i upper hand: `a > 0, b < 0, |a| > |b|` → **Compromise+**, j moves part way to i:
    eq. 35: `x̂ = (x_i − x_j) · |E^j(U_ji) / E^i(U_ij)|`; new `x_j = x_j + x̂` (→ `x_i` as ratio→1,
    → no move as ratio→0).
  - j upper hand: `a < 0, b > 0, |b| > |a|` → **Compromise−**, i moves part way to j:
    eq. 36: `x̂ = (x_i − x_j) · |E^i(U_ij) / E^j(U_ji)|`; new `x_i = x_i − x̂`.
    (Text prints "`b < 0`" for the j-upper-hand clause; figure 6 places Compromise− at `b > 0`.
    See A3 — we follow the figure/symmetry.)
- **Compel / Capitulate** (fig. 6 only): the larger-|EU| dominance taken to a full move.
  - `a < 0, b > 0, |a| > |b|` → Compel−: **i moves fully to j**.
  - `a > 0, b < 0, |b| > |a|` → Compel+: **j moves fully to i**.
- **Status quo / Stalemate** (fig. 6 only): `a < 0 and b < 0` → **no one moves** (i stays put).

### §6.2 Offer selection (p. 26)
"Each player would like to choose the best offer made to it… Given equally enforceable
proposals, players move the least that they can." Order for actor i (so i moves least): (1)
conflict with j; (2) compromise to j (loses some ground); (3) acquiesce to j (loses most);
(4) stalemate (status quo). "if actor i is in conflict with several… it will need to concede
to the one that allows i to move the least." If offers are not equally enforceable, "concede
to the actor with highest expected utility."
**Operationalized:** each actor takes, among all dyads in which it is the mover, the offer
requiring the **smallest |Δx_i|**; if none require it to move, it stays. (See A4.)

## §7 Results — the replication target (pp. 27–28)

Table 1 = BDM 1994 emission-standards input (transcribed to the fixture).
`Q = 1.0`. Reported by Scholz:
- **Table 2 — median voter position by round**: `8.4, 9.9, 9.9, 9.9, 9.9, 7.4, 8.8, 9.6`.
- **Table 2 — mean voter position by round**: `7.4, 7.5, 7.6, 7.3, 7.3, 7.4, 7.5, 7.6`.
- Text: "the median voter position at the end of the first round to be 8.4 years. At the end
  of the second, third, fourth and fifth rounds the median voter position was for each 9.9
  years." (p. 28)
- BDM's own reported outcome: dominant lag 8.35 years, rising to 9.05 and stabilising; actual
  resolution 8.833 years (p. 98, quoted p. 27). Median "appears to stabilise, but then
  continues to change" — the convergence ambiguity our §4-step-8 stopping rule addresses.

Quadrant-accuracy of Scholz's reproduction vs. BDM's published figures: 100% (p. 27).

---

## Flagged ambiguities (resolve by replication; log resolutions as D2.x in DECISIONS.md)

- **A1 — leading salience in E^j(U_ji).** eq. 6 uses `s_j` (responder). By i↔j swap, `E^j(U_ji)`
  uses `s_i`. Appendix step 7's printed second line is small; we adopt the responder-salience
  reading (eq. 6 derivation). *Confidence: high.*
- **A2 — security-sum superscript.** Appendix step 8 / eq. 34 print `E^i(U_ji)` (i's EU as
  responder), but §5 text defines security as "utility adversaries expect from challenging i"
  = `Σ E^j(U_ji)`. We test both; the challenger-EU reading `Sec_i = Σ_{j≠i} E^j(U_ji)` matches
  the prose. *Confidence: medium.* (Irrelevant only if risk is disabled.)
- **A3 — Compromise j-upper-hand sign.** Text prints `E^j(U_ji) < 0`; figure 6 shows
  Compromise− at `E^j(U_ji) > 0`. We follow the figure/symmetry (`b > 0`). *Confidence: high.*
- **A4 — offer selection & compel/stalemate boundaries.** Compel/Capitulate/Stalemate/Status-quo
  region boundaries are figure-6-only (no inequalities in text); offer selection ("move the
  least" vs. "concede to most powerful") is prose. We implement least-movement selection and
  the full-move compel limits above. *Confidence: medium — the primary replication risk.*
