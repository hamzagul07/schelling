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

---

## Session 4 — knowledge index + CLI (BUILD_PLAN §7-9)

### D4.1 — Raw draws stay embedded in the record (a cache, not the source of truth)
Per the Session-3 ruling, `ForecastRecord.outcome_distribution` keeps every raw draw. The
record is fully **recomputable** from `(inputs_hash, solver_config, seed, engine_version)` —
the solver and MC layer are deterministic — so the embedded draws are a convenience cache for
readers/plotting, not the authoritative artifact. If size ever bites, they can be dropped
without information loss and regenerated from the four keys.

### D4.2 — Ensemble statistics moved into a named `ensemble` block (one name, one meaning)
Per the Session-3 ruling, no field name may change meaning by layer. Previously
`ForecastRecord.forecast_median`/`forecast_mean` held *ensemble* statistics while
`SolverResult.forecast_median`/`forecast_mean` held *single-run* statistics — the same names,
two meanings. `ForecastRecord` now carries an explicit `Ensemble` block
`{median, mean, p10, p90, n_draws}` and no longer has `forecast_*`, `ci80`, `settlement_point`,
or top-level `n_draws`. `SolverResult.forecast_*` (one deterministic run) is now the only
thing called `forecast_*`. Minimal change; replication and all prior tests stayed green.

### D4.3 — Source material is detailed lecture *summaries*, not verbatim transcripts
`data/transcripts/` holds three files of structured, AI-generated *summaries* of the
"Predictive History" YouTube game-theory series (Professor J), ~10 lectures each, 29 total.
They apply game-theory framing to geopolitics; they are not verbatim classroom transcripts and
not academic derivations. Consequences: (a) classic terms ("war of attrition", "prisoner's
dilemma") rarely appear verbatim, so lexical search is weak and semantic (bge-m3) search is
what makes retrieval useful; (b) `templates.yaml` cards state standard game theory in the
`solution_concept`/`conditions` and cite the best-matching *application* lectures as
`transcript_refs` — flagged DRAFT pending Hassan's hand-review.

### D4.4 — Lecture heading detection (unambiguous) and chunk provenance
Every lecture is a standalone line `Game Theory #N: <Title>`; we split on
`^Game Theory #(\d+): (.+)$` (anchored at line start, which excludes body sentences that quote
a title). The pattern is consistent across all 29 lectures, so we indexed without pausing for
confirmation (the full list is in the session summary). Each chunk stores its source file, its
lecture name (the citation ref, so results cite lectures not filenames), and exact character
offsets into the source file (verified by a round-trip test).

### D4.5 — Token budget approximated as words × 1.3 (no tokenizer dependency in the chunker)
Chunks target ~800 tokens with 15% overlap. To keep the chunker independent of the heavy
bge-m3 tokenizer, tokens are estimated as `words × 1.3` (typical English ratio) → ~615
words/chunk, ~92 overlap. Windows are word-boundary aligned so offsets stay exact. The 29
lectures produced 71 chunks.

### D4.6 — Pluggable embedder: bge-m3 in production, deterministic hashing for tests/offline
`Embedder` is a small protocol; the index records which embedder built it (in `meta`) so
`search` auto-selects the match. `BgeM3Embedder` (local, lazy-imports `sentence_transformers`,
downloads ~2GB on first use — the `knowledge` extra) is the production default and built the
committed-workflow index (real semantic search, cosine scores ~0.45-0.59 on topical queries).
`HashingEmbedder` — a deterministic, dependency-free bag-of-token-hashes embedder — backs the
tests and offline/CI use, so nothing in the test suite needs torch or a network. Both return
L2-normalized rows; sqlite-vec stores them in a `vec0(... distance_metric=cosine)` table behind
`KnowledgeIndex.search`, so Phase 2 can swap in pgvector without touching callers.

---

## Session 5 — the formalizer (Phase 1)

### D5.0 — Distribution reframed to a private, personal-analysis edition
Per the Session-5 brief, the project is now a **private, personal-analysis edition**; public
release and the public scoreboard are deferred. BUILD_PLAN §9 and the README are updated; the
AGPL-3.0 license and the guiding principle are unchanged. (The GitHub repository's technical
*visibility* is a separate question — the account cannot host a private repo without the repo
being disabled, per the Session-4 finding — so the framing lives in the docs; see the session
summary's open question.)

### D5.1 — Normalizer strips AI-summary boilerplate; offsets rebase to normalized text
The transcripts are AI-generated *summaries* (D4.3), each opening with a generic scaffolding
line ("Here is a comprehensive summary of the video…", "Based on the transcript…"). These
carry no game-theory content and dilute the embeddings, so `normalize_document` strips them
(28 lines across the 3 files, ~1 per lecture) before chunking. Consequence: chunk character
offsets are now relative to the **normalized** text (round-trip verified against
`normalize_document(source)`), not the raw bytes — an accepted trade for cleaner retrieval.
Re-indexed with bge-m3: 71 → 70 chunks. Lecture headings are never matched by the stripper.

### D5.2 — Concepts-library firewall: shingle + code detection over the factual surface
Behind the prompt-level rule (f), a deterministic post-check (`firewall.py`) verifies no
retrieved-concept content reached a *factual* field. The "factual surface" is actor ids/names,
evidence source+note, and assumptions — **not** the template rationale, where citing the
concept library is the whole point. A leak is (a) a **3-word shingle** present in the concepts
text and the factual surface but absent from the supplied facts, or (b) a distinctive
**alphanumeric code** (letter *and* digit, e.g. `b52`). Bare numbers (`20`, `2035`) are
deliberately excluded — they are ubiquitous and caused a false positive on the first live run
(the firewall flagged `20/40/80` from lecture timestamps). Multi-word factual leaks are the
real risk and the shingle check catches them robustly; single distinctive proper nouns leaked
in isolation are left to rule (f) in the prompt (documented limitation). Fail-closed: any leak
raises `IndexLeakageError` and no draft is emitted.

### D5.3 — Formalizer architecture: injectable client, retry loop, adaptive thinking, cost log
- **Injectable `LLMClient`.** `AnthropicClient` (production; lazy-imports the SDK, adaptive
  thinking, default `claude-opus-4-8`) and `ReplayClient` (deterministic, for tests) sit behind
  one protocol, so **CI never calls the live API** (rule 2) — tests replay a recorded draft
  from `tests/fixtures/formalize_replay.json`.
- **Strict JSON + bounded retry.** The model is asked for a bare JSON object; the formalizer
  extracts it, validates against the pydantic `DraftExtraction`, and on `JSONDecodeError` /
  `ValidationError` re-prompts with the error, up to `max_retries` (default 2) extra attempts,
  before raising `FormalizeError`. Token usage accumulates across attempts.
- **Cost logged into the draft.** `DraftMetadata` records model, input/output tokens, USD cost
  (Opus 4.8 $5/$25 per 1M), retries, and an optional timestamp (left `None` for reproducible
  test drafts). The sample EU-ICE-ban run cost **$0.097** (3917 in / 3095 out, 0 retries).
- **Index = concepts only.** The knowledge index supplies template cards + top-k chunks as
  *conceptual grounding* in a clearly-delimited prompt section; facts come only from the
  situation text and sources. `formalize` **never auto-solves** — editing the JSON and running
  `schelling solve` is the sole path to a forecast (human in the loop by construction).

---

## Session 6 — the report renderer

### D6.1 — `ForecastRecord` embeds the input game + median trajectory (self-describing reports)
The Session-6 brief wants a `ForecastRecord` report to show the actor map, the inputs table, and
the per-round median trajectory — none of which the record previously carried. Rather than have
the report re-run the solver, we embed the source of truth in the record: `game` (the original
`GameSpec`, ranges intact) and `median_trajectory` (the deterministic mode-game per-round
median, one extra solve in `build_forecast_record`). Both are added fields with defaults, so
existing tests and records stay valid; a legacy record with `game=None` still renders (the
actor-map and inputs sections are simply omitted). The report is then a **pure, deterministic
function of the artifact** — no solver, no config reconstruction.

### D6.2 — Deterministic rendering (rule 2 applies to reports)
Same artifact → byte-identical HTML. No wall-clock anywhere: `engine_version`, `inputs_hash`,
`created_at`, and every number are read from the artifact, never regenerated. SVG coordinates
are formatted to a fixed 2 decimals (with `-0.00` normalized to `0.00`); `solver_config` and
provenance keys are emitted in sorted order. Golden-file tests (`tests/fixtures/report/*.html`)
pin the output for both artifact types; the goldens are regenerated by re-rendering the
committed fixture JSONs, so a renderer change surfaces as a diff.

### D6.3 — Self-contained & offline: inline CSS, inline SVG, no JS, no URLs
One HTML file: all CSS in a single `<style>`, all charts as inline SVG generated in Python
(no JS charting dependency), no external requests. The SVG `xmlns` attribute is deliberately
**omitted** — inline SVG in an HTML5 document is placed in the SVG namespace by the parser, and
dropping it keeps the report free of any URL-shaped string, so the offline test can assert the
document contains no `http(s)://`, `src=`, `<link`, `@import`, `url(`, or `<script`. Palette is a
restrained neutral grey with a single amber accent for the settlement/median markers; a
`@media print` block flattens margins for clean printing.

### D6.4 — Actor-map axis auto-scales to the data range (not hardcoded 0-100)
Positions are nominally on a 0-100 Policon scale, but the BDM-1994 replication fixture uses raw
years (4-10). The actor map therefore auto-scales its axis to the data range (padded), with the
continuum anchors shown in the header rather than pinned to axis ends — so both a 0-100 draft
and the year-scale replication record render correctly. Dot area ∝ capability×salience (radius ∝
√weight), whiskers span the position low-high range, and the settlement marker (ForecastRecord
only) is a dashed amber line at the ensemble median.

---

## Session 6.5 — firewall calibration + env loading (hotfix)

### D6.5 — `.env` auto-loaded at CLI startup; a missing key is a sentence, not a traceback
A typer `@app.callback()` runs `load_dotenv(find_dotenv(usecwd=True))` at startup, so a project
`.env` (holding `ANTHROPIC_API_KEY`) is found automatically. `usecwd=True` is deliberate:
python-dotenv's default searches upward from the *calling module's* directory (which would find
the package's own tree), whereas we want the directory the user runs `schelling` from. When the
**live** client is used (`type(client).__name__ == "AnthropicClient"`, so a test-injected replay
client is exempt) and no key is present, `formalize` prints one friendly sentence pointing at the
env var / `.env` and exits 2 — never a stack trace.

### D6.6 — Firewall recalibrated: 4-grams + stopword/theory-vocab distinctiveness (fixes false positives)
The first real run flagged the generic trigrams `'of the future'` and `'shadow of the'` — repeated
-games *analysis vocabulary*, not facts. Fix, without weakening true-positive detection: (a) phrase
shingles are now **4-grams**; (b) a shingle is a leak candidate only if it has **≥2 tokens that are
neither stopwords nor canonical theory terms**; (c) the theory whitelist is built from
`templates.yaml` (card names + `solution_concept` text), so terms like `future`/`cooperation`/
`bargaining` are treated as analysis language. Under this rule "shadow of the future" has only one
distinctive token (`shadow`; `future` is whitelisted, `of`/`the` are stopwords) → not flagged;
the planted fact "Zorbian Federation fields nine hundred hypersonic interceptors" keeps four
distinctive tokens per shingle → still flagged. The alphanumeric-code check (letter *and* digit)
is retained. Regression-tested both directions.

### D6.7 — Leak ergonomics: located leaks, a rephrase retry, and a quarantine file
`IndexLeakageError` now carries structured `Leak(phrase, location)` entries and the rejected
`DraftExtraction`; `find_leaks` attributes each leak to its actor and field (e.g.
`actor 'aland' evidence[0].note`). On a leak, `formalize` retries **once** (`max_leak_retries=1`),
feeding the flagged phrases back to the model ("rephrase without these phrases in factual
fields"), then **fails closed**. `DraftMetadata.leak_retries` counts these (distinct from
validation `retries`). The CLI writes the rejected draft to `<output>.quarantine.json` and prints
the located leaks, so a human can inspect exactly what was blocked.

---

## Session 6.6 — wire the draft into solve (hotfix)

### D6.8 — `solve` accepts a DraftGameSpec; assumptions + formalizer provenance run end-to-end
`schelling solve` now accepts **both** a bare `GameSpec` (test fixtures) and a `DraftGameSpec`
(formalizer output). For a draft it solves `.game` and carries the draft's `assumptions` and
formalize-call metadata into the `ForecastRecord` (new fields `assumptions` and
`formalizer_metadata`, defaulting empty/None so bare-GameSpec runs and legacy records are
unchanged). The forecast report then renders an "Assumptions carried from the draft" checklist
and a formalizer line in the provenance footer, closing the chain formalize → solve → report.
**Layering:** `Assumption` and `DraftMetadata` moved to `schemas/forecast.py` (a core contract)
and are re-exported from `formalizer/schemas.py` — importing the formalizer package *into* the
core schemas would have pulled the whole formalizer + knowledge (sqlite-vec/torch) stack into any
solver/MC import, which is wrong; keeping the shared models in `schemas` avoids that inversion.

### D6.9 — Friendly input errors on `solve` (no pydantic tracebacks)
`_load_solve_input` sniffs the artifact by shape (`{game, assumptions, template_classification}`
→ draft; else GameSpec) and, on a `ValidationError`, raises a single-sentence `ValueError` that
says what the file looks like and what `solve` expected (e.g. "looks like a DraftGameSpec … but
does not match the schema (metadata: field required); re-run `schelling formalize`"). The command
catches it and exits 2 — never a traceback, the same pattern as the missing-key path.

### D6.10 — Report renders every current record; old ones fail with a named reason
The `runs/…WIDENED….json` that reported "unrecognized artifact" was a **stale Session-3 record**:
old schema (`forecast_median`/`ci80`, no `ensemble`, no `game`). The current engine writes
`ensemble` records that render fine (the golden proves it). Detection is now robust: a file that
*looks* like a ForecastRecord (`run_id` + one of `ensemble`/`forecast_median`/
`outcome_distribution`) is validated, and on failure raises a **named** reason — a pre-`ensemble`
file says "older schema (~Session 3); re-run `schelling solve`", anything else reports the first
schema error. The stale record was regenerated in place (same `inputs_hash` → same filename) so
it now renders.

---

## Session 7 — advise mode

### D7.0 — Housekeeping: one install command, no silent extra-thrash, friendly missing-extra
(a) The `analyses/` line (local situations/sources/drafts) is committed to `.gitignore`.
(b) **`uv sync --all-extras` is the one documented install command** (README + CI). A partial
`uv sync --extra X` installs *exactly* X and removes the others — that thrash bit earlier
sessions (a `--extra formalize` sync silently uninstalled the `knowledge` torch stack). Using
`--all-extras` everywhere makes the environment always complete; tests still need only base+dev
(they inject fakes), and uv's cache absorbs the torch cost in CI. (c) When the `knowledge` extra
is absent, `knowledge build/search` and `formalize` catch the lazy `ImportError` and print one
sentence with the fix (`uv sync --all-extras`); `formalize --no-knowledge` proceeds ungrounded.

### D7.1 — Advise mode: a one-sided lever search, benefit and cost kept separate
`schelling advise <artifact> --actor <id>` accepts the same artifact types as `solve`. It sweeps
the actor's **own moves** — position across the realized continuum (grid step 5) and salience
down to a floor (20) and up to 100 — and, for every **other** actor, one feasible shift of its
position and salience *toward the advisor's ideal* (within that actor's stated range). Every
candidate is solved with the **same derived seeds** (`run_monte_carlo(seed=…)`), so a difference
in settlement is attributable to the move alone. For each move we report **benefit**
(`|median_before − ideal| − |median_after − ideal|`, ideal = the actor's mode position) and
**cost** (position distance conceded; 0 for salience) **separately — never a single score**.
Moves outside the actor's stated low–high are flagged "beyond stated range". The top-3 own moves
are re-solved at `--target-draws` for final numbers; persuasion targets are ranked by benefit —
the "who to work on" list. On the widened fixture advising germany (ideal 4, baseline 7.92): the
only own lever is raising salience (→100, benefit +0.28, but beyond its point range), and the
standout target is **france.position 10→8 (benefit +0.955)**. Runtime ≈ 69 s at defaults
(2000 draws/candidate, 10k target).

### D7.2 — Position sweep is data-driven (not hardcoded 0-100)
The sweep range is the *realized* continuum — `[min(actors' pos.low), max(actors' pos.high)]` —
so it is correct both for a 0-100 game and for the year-scale replication fixture (~2-12). The
salience sweep is `[salience_floor, 100]`. Grid step is configurable (default 5).

### D7.3 — `AdviseRecord` artifact + report, deterministic and caveated
`AdviseRecord` (in `schemas/forecast.py`) carries the advising actor, ideal, the baseline
reference (`baseline_run_id` + `baseline_median`), the full own-move and persuasion-target tables,
top moves, seeds, `advise_config`, `solver_config`, `inputs_hash`, engine SHA, and the game (for
the report's baseline map). Same inputs + seed → byte-identical record (rule 2). `schelling
report` renders it: baseline actor map with the settlement marker, an own-moves benefit-vs-cost
scatter, a persuasion-target bar ranking, and — printed on **every** advise output (CLI and
report) — the standing caveat: *"One-sided search: opponents are held to the model's fixed
behavior; real adversaries adapt. Treat as lever-finding, not a playbook."*

---

## Session 8 — live search in the formalizer

### D8.0 — Advise refinements: adaptive position grid + energize/defuse labels
(a) The position sweep's default step is now **adaptive**: the realized continuum span / 20, so a
year-scale game (~2–12) and a 0-100 game both get ~20 candidate points without hand-tuning.
`--grid-step` still overrides (and, when given, applies to both the position and salience sweeps,
as before). Salience keeps a fixed default step of 5 (it always lives on the 0-100 scale). The
*effective* steps are recorded in `advise_config` (`grid_step`, `salience_step`) so the record
stays self-describing and reproducible. (b) Each persuasion-target row is labeled **energize**
(raise an actor's salience, or pull its position toward the advisor's ideal) vs **defuse** (lower
an actor's salience). Position targets are always `energize`; a salience target is `energize` when
the chosen edge raises salience and `defuse` when it lowers it. The label surfaces in the CLI,
the report table (new "play" column), and the persuasion bar labels.

### D8.1 — `formalize --search`: server-side web search, fetched pages are evidence
`schelling formalize --search [--max-searches 5]` enables Anthropic's server-side web-search tool
(`web_search_20260209`, `max_uses = max_searches`) in the formalize call, so the model may fetch
current sources *before* drafting. Everything it fetches is **evidence-river material**, on the
same footing as a supplied source file: each fetched page becomes a `FetchedSource`
`{url, title, retrieved_at, snippet}` in `draft.sources_fetched`, and an evidence note may cite a
fetched page exactly like a supplied file. Cost: the search is billed at $10 / 1,000 searches
(Anthropic list price); `searches_used` and the combined token+search `cost_usd` are logged in
`DraftMetadata`. Search is **off by default** — the deterministic, offline pipeline is unchanged
unless the flag is passed.

### D8.2 — The thin client parses multi-block responses; `retrieved_at` is evidence metadata
`AnthropicClient` now assembles a completion from a *multi-block* response: `text` blocks (joined),
`server_tool_use` (the query, ignored), and `web_search_tool_result` (a list of `web_search_result`
items → `WebSource(url, title, snippet)`, snippet taken from the text blocks' citations — the
passage Claude actually quoted). `searches_used` is read from `usage.server_tool_use.
web_search_requests`. A rejected tool (account not enabled / bad type) is mapped to a friendly
`WebSearchUnavailableError` ("re-run without --search"), never a raw traceback. `retrieved_at` is
stamped from the run date (`today`, injected by the CLI; fixed in tests): it is **data about the
evidence**, deliberately kept out of any hash and out of report layout, so determinism (rule 2) is
untouched — a live-searched draft is byte-identical given the same `today` and replayed sources.

### D8.3 — Freeze discipline: a live-searched draft is stamped today, and backtests forbid search
With `--search` on, `game.frozen_at` is forced to `today` and `DraftGameSpec.live_searched` is set
— a live search returns today's web and cannot honestly be frozen in the past. CLAUDE.md gains
**rule 7**: historical backtests (the Phase 2 ICB harness, any calibration on resolved cases) must
run with search OFF, or they leak the future. The firewall is unchanged in spirit: fetched title +
snippet text joins `allowed_text`, so a fact that arrives via a fetched source is allowed in a
factual field (it *is* evidence), while concept-library content that is *not* in any fetched source
stays blocked. Tested both directions: the same distinctive fact is a leak when it exists only in
the concept index, and legitimate evidence once it also appears in a fetched snippet.

### D8.4 — Report renders `sources_fetched` as a linked source list; still offline-clean
`render_draft` adds a "Sources fetched — live web search" section (and a `live-searched` badge in
the header) listing each source as a clickable link with its `retrieved_at`. This introduces
`https://` hyperlinks into the report, which the strict Session-6 offline test banned outright. The
guarantee that matters is "opens offline, loads nothing": a hyperlink to a cited source loads
nothing until clicked, whereas the real risks are *resource-loading* tokens. So the searched-draft
report is tested to contain **no** `<script`, `<link`, `src=`, `@import`, or `url(` while allowing
`href="https://…"`; the three source-less goldens keep the original strict no-URL assertion. Source
rows render in a deterministic order (by URL), independent of fetch order.

---

## Session 9 — the DEU backtest (Phase 2)

### D9.0 — Session-8 carry-overs
(a) `live_searched` is now carried draft → `ForecastRecord` → report, exactly as `assumptions`
are (D6.8): `_load_solve_input` returns it, `forecast()`/`build_forecast_record()` thread it, and
`render_forecast` prints a caveat that the inputs rest on a live search, not a frozen snapshot.
(b) A fetched source with no snippet (Claude retrieved but never quoted it) is labeled "retrieved,
not cited" in the report, so a reviewer sees the citation is weaker than a quoted one. (c) The
search prompt gained one line preferring a few authoritative **primary** sources over many
secondary ones, and citing the passage actually relied on.

### D9.1 — DEU III dataset located, ingested; no manual step needed
The benchmark is the **DEU III** dataset (Arregui & Perarnaud 2021, *A new dataset on legislative
decision-making in the EU*), the current open-access successor to Thomson/Stokman/Achen/König's DEU
I/II. It is **CC BY 4.0, direct-download, no registration** from the CORA/CSUC Dataverse
(`doi:10.34810/data53`), so no manual step was required — the four files were fetched into
`data/deu/` (gitignored; not redistributed here). The CSV is semicolon-delimited, one row per
issue, with each actor's position and salience on a 0-100 scale, a reference point `rp`, and the
actual outcome `out`. `deu.py` normalizes it: values outside [0,100] are missing-data sentinels
(e.g. `999`); rows without a valid outcome or with fewer than 3 participating actors are dropped,
leaving **351 scoreable issues** of 364. The exact CSV is pinned by SHA-256 in every record.

### D9.2 — Capability: DEU records none, so every actor gets an equal fixed value (100)
DEU provides position and salience per issue but **no capability**. Rather than import external
Council voting-weights (which vary by enlargement period and procedure and would themselves need
sourcing), every actor is assigned a fixed capability of 100. This is the assumption-light choice:
with equal capability the "capability×salience weighted mean" baseline is the salience-weighted
mean — a classic DEU 'compromise' model — and the solver's added value must come from its
position+salience **bargaining mechanism**, which is exactly what the backtest is meant to test.
Limitation logged: a voting-weight capability could change the absolute MAEs (of both the solver and
that baseline); the published comparisons that used influence weights show the same *ordering* we
find, so the negative result is not an artifact of this choice. `--capability` overrides it.

### D9.3 — Point estimates → one deterministic solve per issue (`--draws` is nominal)
Each DEU issue is point estimates, so Monte Carlo is degenerate (every draw identical, zero
variance — D3.1). The harness therefore solves each issue **once** with the deterministic solver
(`run(game, cfg).forecast_median`) instead of repeating 2000 identical draws (which would be
~2000× slower for no change). `--draws` is accepted and recorded for interface parity but does not
affect a point-estimate result. Search is never involved (CLAUDE.md rule 7). Same inputs + seed →
byte-identical `BacktestRecord`.

### D9.4 — The gate (fixed in advance) and the verdict: FAILED — a negative finding, honestly
**Gate (stated before running):** the solver's paper-faithful config must beat **both** naive
baselines — the capability×salience weighted mean and the median actor position — on MAE across all
351 issues. **Verdict: FAILED.** On the full set: solver (paper-faithful) MAE **28.31**; median
baseline **28.37** (solver narrowly beats it); capability×salience weighted mean **23.64** (solver
**loses**). Risk-off is worse (29.08); the R×Q sweep moves MAE only within 28.3–28.7. This is not a
surprise — it **reproduces the canonical DEU finding**: Achen (2006, in Thomson et al.) showed the
influence-and-salience-weighted mean predicts EU outcomes as well as or better than the more complex
bargaining/procedural models, and Bueno de Mesquita's own tests (2011, CMPS 28(1)) put his "Old
Model" (the expected-utility/challenge model our solver reconstructs) at MAE ≈ 21–28, losing to the
weighted mean (≈ 12–19). Our numbers sit squarely in that regime with the same ordering. Per the
brief, the negative result is written up plainly in `BACKTEST.md` rather than papered over — the
mechanism does not (yet) earn its keep on legislative EU bargaining under equal capability.

### D9.5 — Deterministic write-up + report; published context cited, not fabricated
`schelling backtest data/deu/` writes a `BacktestRecord` (per-method MAE/RMSE/median/max + full
per-issue error lists + worst-N + gate verdict; `created_at` defaults None, dataset pinned by
SHA-256 → byte-identical under a fixed seed), a `BACKTEST.md`, and (optionally) an HTML report
(error histogram, per-method MAE bars/table, worst-10, published-context table). The published DEU
error rates are taken from the sources fetched this session (BdM 2011 Tables 1 & 3 via the paper
PDF; Achen 2006; the DEU III data paper) and are clearly flagged as **not directly comparable**
(different DEU version, issue subset, capability/resolve handling) — cited to show the regime and
the known ordering, not as a like-for-like benchmark. The report is a new artifact type in
`render()`; four goldens were refreshed for the added CSS.

---

## Session 10 — the fair fight (Phase 2)

### D10.0 — Session-9 carry-overs (Session 8 review items)
Already covered in D9.0; no new work this session. (Kept for numbering continuity.)

### D10.1 — Sourced capability table (real Council power, both sides)
DEU records no capability (Session 9 used equal=100). The published DEU convention is the
Shapley–Shubik power index (Arregui, Stokman & Thomson 2004, *European Union Politics*, p. 592;
confirmed by pdftotext of the source PDF this session). Per Hassan's approval we use the transparent,
fully-citable **approximation**: each member state's capability is its Council power under the treaty
regime in force at the issue's decision date, rescaled so the strongest actor = 100 (Policon).
Sources: pre-Nice EC weights (total 87; Treaty establishing the EC, art. 148 Amsterdam
consolidation), Treaty of Nice weights (EU-27 total 345; OJ C 80 2001), Lisbon-era populations
(double majority has no vote weights, so population is the proxy; Eurostat via Wikipedia, retrieved
2026-07-21). Self-check assertions pin the 87 and 345 totals. The SAME table feeds the challenge
solver and the weighted-mean baseline — the "fair fight" (equal treatment). This is *restoring
inputs*, not a model modification, so it does not need split-sample validation.

### D10.2 — Period mapping by decision date (unambiguous cutoffs)
Each issue's regime is chosen by its `finact` (final-act) year: ≤2004 pre-Nice, 2005–2014 Nice,
≥2015 Lisbon. The DEU decision-date distribution clusters cleanly (1998–2001, 2005–2009, 2016–2019)
with empty gaps at 2002–2004 and 2010–2015, so no issue lands on a cutoff boundary.

### D10.3 — Commission & EP capability = the largest member-state weight (Hassan's decision)
The Commission and EP have no Council vote, so their capability is a modeling choice. Hassan chose
"largest-state weight each," so both normalize to 100 in every regime — heavy unitary actors. (The
DEU SSI instead folds them in via procedure-specific co-legislator roles; we deliberately took the
simpler, transparent rule and recorded it for approval rather than computing the SSI ourselves.)

### D10.4 — The reference-point (rp-anchored) challenge variant
`SolverConfig.reference_point` (default None). When None the status quo is "no move" (`u_sq` at
distance 0, Scholz eq. 24 — unchanged, so the replication stays 9.53 bit-for-bit). When set, the
reversion outcome is that continuum point, so `u_sq_i = 2 − 4(0.5 + 0.5·min(|x_i − rp|/R, 1))^r`:
an actor's status-quo utility falls with its distance from the reference, making distant actors more
willing to move. Wired scalar (`basic_utilities`) and vectorized (`eu_matrix`, per-challenger
column) and threaded from config through `rounds`. On the DEU rp-issues this is fed each issue's DEU
reference point. This IS a model modification, so its Q is tuned split-sample (D10.7).

### D10.5 — The compromise model as a first-class solver (ship the winner)
The compromise model — the capability×salience weighted mean (Van den Bos 1991; a first-order Nash
bargaining approximation, Achen) — is now a first-class forecaster in the MC layer:
`ForecastRecord.model` ∈ {"challenge", "compromise"}, `run_monte_carlo(model=…)` computes the
weighted mean per draw (so it gets a real CI80 from the triangular draws), and `run_id` carries a
`-compromise` tag. `schelling solve --solver challenge|compromise|both` (default **both**) reports
them side by side; the report names the model in its header. This makes the DEU winner a shippable
model, not just a baseline column.

### D10.6 — The forecast ledger (FORECASTS.md)
`schelling ledger <game> --grade-date` seals BOTH models' forecasts for a real, unresolved question
into `FORECASTS.md`, to be graded later. `forecast_commitment` hashes only the substantive
prediction (question, model, inputs_hash, seed, ensemble) — **excluding** engine SHA and timestamps —
so the same inputs + seed reproduce the same commitment across engine commits. The sealed game files
stay out of the public tree; only the forecasts + hashes are committed. First entry: the sealed
US-Iran stage-two game (`Q-2026-USIRAN-STAGE2`, frozen 2026-07-21, anchored to House of Commons
Library CBP-10637) — challenge 34.576 vs compromise 41.636 on the 0=US/100=Iran continuum, graded
**2026-09-01**. Two models, one event.

### D10.7 — Gate v2 (fixed in advance): the challenge solver still loses the fair fight
**Gate v2 (immovable, stated before running):** with real capabilities and the reference point, the
challenge solver must beat the equally-equipped weighted mean on DEU MAE; any model change beyond
restoring inputs is validated split-sample (tune Q on the even-indexed half, score on the odd half).
**Verdict: FAILED.** Full 351-issue set: sourced capabilities improved *both* models (challenge
28.31→27.94, weighted mean 23.64→**22.99**); the rp-anchored challenge (split-sample-selected Q=0.7)
improved the challenge further to **26.83**, and the split-sample confirms this is real, not overfit
(held-out test MAE 26.07 vs the weighted mean's 23.32 — the rp gain holds but still loses). So the
fair fight *narrowed* the gap (challenge 28.31→26.83) yet the compromise model wins by ~4 MAE,
exactly as Achen/BdM predict. The reference point helped but did not collapse the pole-stampede
failures (max error stays 100 on the worst issues). A robust negative finding, written up in the
now-living `BACKTEST.md`. **The ICB coercive benchmark is scheduled next regardless** — EU
legislative bargaining is the cooperative setting BdM notes his model handles worst; ICB (coercive
interstate crises) is where the mechanism should have its best shot, and that test decides more than
this one.

---

## Session R1 — the successor search (Phase 2)

### R1.0 — Pre-registration: the split is committed before any model is fitted
The DEU issues are cut 40/30/30 into train/dev/**TEST** by a seeded hash of the issue id (seed
20260721 → train 140, dev 105, TEST 106; rp-issues 103/70/79), exact counts, order-independent. The
assignment is written to `deu3_split.json` and **committed as its own commit, ahead of any candidate
code** (git history is the audit trail). The TEST split is scored **exactly once**, at the very end;
model selection (L2) uses dev only. Feature standardization uses train statistics only — no dev/TEST
leakage.

### R1.1 — Candidate A: status-quo gravity
`outcome = λ·wmean + (1−λ)·rp` on the rp-issues, with `λ = sigmoid(bias + β·standardized[rule_cod,
herfindahl, rp_dist])`. Fit by deterministic full-batch Adam in pure numpy (no sklearn/scipy
dependency; byte-identical, rule 2) on train rp-issues; L2 chosen by dev MAE (→ 1.0). Idea: let the
outcome gravitate from the compromise mean toward the status quo where structure says it should.

### R1.2 — Candidate B: regime-aware settlement
Softmax regime weights `π = softmax(W·[1, standardized(gini, polarization, rp_offset, n_actors,
rule_cod)])` over three regimes (compromise / challenge / status-quo); prediction is the π-weighted
blend of the three component estimates — the compromise weighted mean, the Session-10 real-input
challenge solver, and the status-quo reference point (falling back to the weighted mean where no rp
exists). Fit by Adam on all train issues (MSE, differentiable mixture-of-experts; no observed regime
labels); L2 by dev MAE (→ 1.0).

### R1.3 — The gate (immovable): both candidates FAIL on the untouched TEST split
Each candidate had to beat the compromise weighted mean on TEST; MAE deltas carry a paired bootstrap
95% CI (seed 20260721). **Verdict: neither beats compromise.** Candidate A (TEST rp-issues, 79):
MAE 22.09 vs compromise 21.26, Δ **+0.83** [−0.15, +1.91]. Candidate B (TEST all, 106): MAE 21.57 vs
21.09, Δ **+0.48** [−0.69, +1.76]. Both point estimates are *worse*; both CIs straddle zero →
statistically indistinguishable from, but not better than, the mean. Candidate B's learned regime
weights collapse onto compromise (≈0.83) — it essentially rediscovered "use the weighted mean," and
the challenge/status-quo components add noise. A robust, pre-registered negative result: the
compromise model remains the settlement model for DEU. Consistent with Sessions 9–10 and the DEU
literature.

### R1.4 — Shipping + the living leaderboard; nothing sealed
Both candidates ship as first-class `schelling solve --solver gravity|regime` options (the train-fit
parameters are committed as `deu3_candidate_gravity.json` / `deu3_candidate_regime.json` and loaded
at predict time; features + components are computed for any game, rp optional). `schelling successor`
runs the whole protocol and writes the leaderboard into `BACKTEST.md` between idempotent markers —
the living leaderboard. **No candidate survived, so nothing was sealed against the live US-Iran game**
(item 4's "surviving candidate" clause did not trigger). The out-of-domain check on the ICB coercive
set is deferred to Session 11 (when that data lands), as specified. Note the out-of-domain fragility
already visible: on US-Iran (features far outside DEU's range) both candidates' softmax/logistic
saturate onto the compromise mean.

---

## Session 11 — the decisive test (Phase 2)

### D11.0 — Noise-floor oracle: the compromise mean is AT the extractable-signal ceiling
A DIAGNOSTIC (`oracle.py`): a deliberately flexible model — the best of linear ridge and RBF kernel
ridge over a RICH 18-feature set that includes position summaries (min/max/std, salience-weighted
quantiles) — fit under seeded 5-fold cross-validation with in-CV hyperparameter selection (an
*optimistic* ceiling estimate). Result on the 351 sourced-capability DEU issues: oracle CV MAE
**23.84** vs the compromise mean **22.99**, gap **−0.84**. The flexible model does not just fail to
beat the mean — it does slightly *worse*. So the mean is at (not merely near) the extractable-signal
ceiling: there is essentially no exploitable signal beyond the influence-weighted average. This
explains why Sessions 9, 10, and R1 all failed to beat it — there was nothing to extract. Reported in
`BACKTEST.md` and the backtest report. Pure numpy, deterministic (rule 2).

### D11.1 — Coercive case library: STOP (paywalled/unfindable); harness built, library deferred
The crown-jewel coercive library (Hong Kong 1985, Iran 1984, Feder's examples, KTAB/Senturion) could
not be assembled: (a) the in-repo Feder (1987) report prints resources (capability) and *diagram*
positions but **no numeric salience** and only qualitative outcomes — incomplete for a real game
without assuming inputs (violating rules 3/6 and "expert-coded"); (b) the named coercive classics are
in **paywalled books/journals** (*Red Flag over Hong Kong*; BDM's Iran article); (c) open replications
(Preana, the umich appendix) cover cooperative/economic or *ex-post election* cases (Iran 2013), not
ex-ante coercive interstate crises. Per the STOP instruction and Hassan's decision ("defer; you'll
provide tables"), the **head-to-head harness is built and validated on a synthetic fixture**
(`coercive.py`: `load_library` + `head_to_head` scoring challenge/compromise/gravity/regime with
paired bootstrap CIs and small-N honesty; `schelling coercive`) and runs the moment real tables land
at `data/coercive/library.json`. **What Hassan should provide:** for each coercive case, the printed
per-actor position/salience/capability (0-100) + the historical outcome on a stated 0-100 continuum +
citation + whether coding was ex-ante — hand-transcribed from the paywalled sources he can access.

### D11.2 — ICB analog / base-rate layer (built; off by default, never blended)
`analog/icb.py`: a feature-tagged, KnowledgeIndex-style retrieval over the **ICB (International Crisis
Behavior) Version 16** actor-level dataset (1,131 crisis-actors, 1918-2021; downloaded from Duke,
`data/icb/` gitignored). A compact table of the used fields (crisis, actor, year, outcome, gravity,
violence, n_actors, power, protracted) is committed as package data (`icb_analogs.json`, cited to
ICB) so the layer ships self-contained. `ICBAnalogIndex.search(gravity, violence, n_actors, k)`
returns the k structurally nearest crises + their historical **outcome distribution** (victory /
compromise / stalemate / defeat) — a base rate. Surfaced as a report panel via
`schelling solve --analog "gravity=6,violence=3,actors=8"`: **off by default**, rendered in a
clearly separated section, and **never blended into the solver settlement line** (`blend_weight` = 0,
disclosed). It is a historical frequency shown alongside — not mixed into — the deterministic
forecast. On a US-Iran-shaped query (gravity 6, serious clashes, 8 actors): 30 analogs → victory 43%,
compromise 30%, defeat 20%, stalemate 7%.

### D11.3 — Domain verdicts, side by side
`BACKTEST.md` now states both: **cooperative (DEU)** — compromise mean wins, challenge loses even
fully equipped, and the oracle shows the mean is at the ceiling; **coercive (interstate crises)** —
**PENDING**, harness built, blocked on paywalled inputs (D11.1). The ICB analog layer is a separate
base-rate tool, not a head-to-head benchmark.

### D11.4 — Coercive library schema + first KTAB registration (follow-up)
The coercive library is now a **directory** of hand-transcribed case files (`data/coercive-cases/`)
with a documented schema (`data/coercive-cases/README.md`): per case a nested `continuum`, a flat
0-100 `actors` table (position/salience/capability), `source`/`ex_ante`/`domain` metadata, a
`transcription.verified` flag, and one or more dated `outcomes` (the `primary`-flagged, or
first-listed, reading is scored; others are secondary — the horizon rule). `coercive.py` was
upgraded to this richer schema (building a `GameSpec` per case) and its loader now reads a directory.
**Registered `ktab-china-2014.json`** — two domestic-elite-bargaining cases from Efird, Lester & Wise
(2016)'s KTAB study (doi:10.1017/jea.2015.4). The harness smoke-runs it (`schelling coercive`), but
it claims **no verdict**: the note fires all three guards — N=2 is tiny, transcriptions are
`verified: false` (draft-1; Claude-proposed outcomes pending Hassan's check against the source), and
the cases are out of the coercive domain (domestic, not interstate). The coercive interstate classics
remain the quest (D11.1); this entry is out-of-domain validation scaffolding, not a coercive verdict.

---

## Session 12 — ledger sealing, retirements, diagnostics (wrap-up)

### D12.0 — FORECASTS.md now seals by SHA-256 of the record file (correction to the old ledger)
The ledger line for a forecast is now pinned by the **SHA-256 of the exact `runs/` record file**
(`ledger.record_sha256` = `sha256(path.read_bytes())`), so a reader can `sha256sum runs/<file>` and
verify. This **supersedes and corrects** the Session-10 ledger, which pinned its two v1 rows by a
*partial* `forecast_commitment` hash (question + model + inputs_hash + seed + ensemble, excluding the
engine SHA/timestamps) and recorded only v1. The correction, stated explicitly in FORECASTS.md: the
hash basis changed from that partial commitment to the record-file SHA-256, and the recomputed
SHA-256s are the source of truth. The forecast **medians were verified unchanged** against the
recomputed records (v1 challenge 34.576, v1 compromise 41.636); only the hash basis moved and v2 was
added. The four sealed records: v1 challenge `…45d931c6cd91` (aece91bd…), v1 compromise
`…2cbb0bc624f3` (c87d91ae…), v2 challenge `…d4441652019a` (3bc97cd4…), v2 compromise
`…d4441652019a` (d55ffc3e…). `forecast_commitment` is kept as a historical utility (still tested) but
is no longer the ledger's hash.

### D12.1 — `schelling seal <record.json>` (one-command, idempotent sealing)
Replaces the old `ledger` command. It reads a `runs/` record, computes its SHA-256, and appends one
markdown row inside the `<!-- LEDGER:START/END -->` block of FORECASTS.md (creating the block/header
if absent). **Idempotent:** if that SHA-256 already appears anywhere in the file, it reports and
changes nothing — re-sealing is safe. `--vintage` sets the vintage label (the record can't carry it).
Records are never committed (`runs/` gitignored); `analyses/` is never touched.

### D12.2 — The Iran-faction-split experiment is formally retired
An earlier US-Iran vintage explored modelling Iran as competing factions. **v2 retired that split:**
it runs a **single `iran` actor**, **adds the IAEA** as an actor, and **renames the Gulf blocs**
(`gulf_hawks` → `uae_hawkish_gulf`, `gulf_moderates` → `moderate_gulf`). The split is retired — not
left dangling — because it added actors whose positions/saliences the sources could not pin down
(inventing them would violate rule 6), and because the single-actor v2 is the cleaner, defensible
specification. Both vintages are sealed in FORECASTS.md for the 2026-09-01 grading, so the choice is
auditable rather than silently dropped: v2 challenge forecasts **29.407** (vs v1's 34.576), v2
compromise **39.443** (vs v1's 41.636) — the revision pulled both models modestly toward the US pole.

### D12.3 — Tornado diagnostics: degenerate-median-lock warning + mode-game median surfaced
Two related transparency fixes prompted by the v2 challenge run (whose deterministic mode game locks
at 22.0 while its Monte-Carlo median is 29.4, and whose tornado is 18/27 zero-swing):
- **`zero_swing_warning`** flags a sensitivity table where ≥ half of (and ≥ 2) the ranged parameters
  leave the forecast unchanged — a "degenerate median lock" where the weighted median is pinned and
  single-parameter moves don't shift it. Printed in `solve` output and shown as a caveat box in the
  report.
- **The deterministic mode-game median** (`median_trajectory[-1]`) is now shown **alongside the MC
  median** in `solve` output and the report headline, with the signed gap, so the reader sees when
  the point-estimate solve and the ensemble diverge sharply (e.g. v1: mode 53.8 vs MC 34.6, gap
  −19.2). The compromise model has no round trajectory, so its mode-game cell reads "—".

### D12.4 — `advise --solver compromise|both`: the exact closed-form lever lens
The compromise model's settlement is the capability×salience weighted mean of positions, so its
levers are **closed-form**, not simulated. Shifting actor *i*'s position by *d* moves the settlement
by exactly `(w_i / Σw)·d`; a salience change re-weights the mean analytically. `advise` now takes a
`model` argument (CLI `--solver`): `challenge` (the default Monte-Carlo simulated search),
`compromise` (the exact weighted-mean levers), or `both` — challenge primary with the compromise lens
attached as `AdviseRecord.second_lens` and rendered **side by side** in the report. Compromise moves
are labeled **"exact"** to distinguish closed-form shifts from the challenge model's simulated MC
search. The sweep/benefit/cost logic is shared (`_lens_moves`, parameterized by a settlement
function), so the challenge lens is byte-identical to Session 7's and its golden is unchanged. The new
`AdviseRecord` fields (`model`, `exact`, `second_lens`) default to `challenge`/`False`/`None`, so
existing records validate and render unchanged. `_compromise_settlement` returns the plain mean of
positions when total weight is zero (degenerate guard). Determinism (rule 2) holds: the exact lens is
a pure function of the game, byte-identical across runs; `run_id` carries the model tag.

### D12.5 — `schelling analyze`: the one-command formalize→solve→report flow with a human gate
`schelling analyze "<question>" [--sources dir] [--search] [--solver both] [--seed 42]` chains the
whole pipeline: formalize the question into a draft, write the draft JSON, print the stakeholder
table, **pause at a human-review gate**, then (on confirm) solve both models, render the report, and
print a five-line terminal summary (medians, CI80s, mode-vs-MC gap, top lever, assumptions count).
The gate is **default-on**: `analyze` stops after the draft and tells the reader to edit the JSON and
run `solve` unless `--no-review` is passed — the LLM structures, the human approves, the math predicts
(rules 1, 6). `--solver` selects `challenge`, `compromise`, or `both` (default). The formalize path is
factored into a shared `_formalize_or_exit` helper (index open, key check, `run_formalize`, and the
`WebSearchUnavailable`/`IndexLeakage`/missing-extra friendly exits) reused by `analyze`; the existing
`formalize` command is left untouched so its tests are unaffected. Search follows rule 7: a
`--search` analyze stamps `frozen_at = today` and marks the draft live-searched; never use it for
backtests.

## Session 13 — blind dual-entry verification of the case library

### D13.0 — The verification protocol: blind dual machine transcription + human ratification
Case-library files (`data/coercive-cases/`) are verified in two separable steps, and the
`transcription.verified` flag is gated on the second, never the first:
- **Blind dual entry (machine).** The source PDF is downloaded into `docs/papers/`, rendered to page
  images, and the stakeholder tables are transcribed **twice, independently, by agents that never see
  the existing JSON**, then diffed against each other and against the file. Where the source prints a
  derived `Exercised Power = Influence × Salience / 100` column it is used as a per-row checksum; the
  `Influence` column maps to the JSON's `capability`, and the derived Exercised-Power column is not
  stored (it is recomputable). A new `transcription.verification_method` field records the protocol;
  `verification_note` records what the diff found.
- **Human ratification (Hassan).** Transcribing numbers is mechanical; the interpretive choices are
  not — outcome codings, continuum wording, and the horizon rule are put to Hassan as explicit yes/no
  questions and are his call. `verified` flips to `true` **only after he ratifies**, with his words
  quoted in `verification_note` — **even when the numeric diff is clean**, because a perfect number
  transcription does not settle a judgment. `verified` remains Hassan's flag alone.

**China (Efird, Lester & Wise 2016, JEAS 16; `docs/papers/efird_2016_china_coalitions.pdf`) — result.**
Numbers are exact: all 26 Policy-Space rows (Table 2) and all 34 Competitive-Space rows (Table 3)
match on position/capability/salience across both blind reads and the JSON; every Exercised-Power
checksum reproduces; actor counts (26/34) and the `capability ← Influence` mapping are correct. Both
continua are faithful — case 1 to Figure 1 (p.129), case 2 to **Figure 6 (p.138)**, whose printed
markers (0 status quo, 10 end-of-patronage, 30 transparent tendering, **60 divest major assets e.g.
pipelines on open access**, 100 break up CNPC) match the JSON, so the Position-60 marker the long-run
coding leans on is genuinely in the paper. Both `published_model_forecast` notes match the paper's
results. The three interpretive judgments — the outcome codings (25/25 near-term, 55/60 long-run) and
the horizon rule — were put to Hassan as explicit yes/no questions; a substantive finding is that
**the paper states no calendar horizon** (its 10 "turns" are bargaining rounds, not years; the only
temporal phrase is "in the near term"), so the `by_2017 / by_2020 / 5-year` framing is a convention we
impose, not the paper's own. **Hassan ratified (2026-07-21):** (a) 25/25 accepted; (b) 55/60 accepted,
with Dec-2019 PipeChina confirmed as the paper's printed Figure-6 Position-60 marker; (c) keep the
2017/2020 readings but **relabel them as our scoring convention**. On that ratification
`transcription.verified` was flipped to `true` and his answers quoted in `verification_note` (the
protocol: numbers alone never flip the flag). The case still claims no coercive verdict — it stays
out-of-domain (domestic bargaining) and N is tiny.

**Japan (KAPSARC KS-2018-DP47) — BLOCKED.** The PDF is not in `docs/papers/`; the scaffold
(`drafts/ktab-japan-2017-scaffold.json`) records the differing column order (Influence | Position |
Salience) and the Exercised-Power checksum to apply. The same blind protocol runs when Hassan supplies
the PDF. Its 5 known rows are internally checksum-consistent but remain unverified against the source.

## Session 14 — Japan (blocked) + the paper scaffold

### D14.0 — Japan case stays BLOCKED; the paper scaffold runs regardless
Part A (the Japan KTAB case) is precondition-gated on the KAPSARC KS-2018-DP47 PDF being present in
`docs/papers/`. It is not (Hassan still owes the 2-minute KAPSARC "download without subscribing"
form), so Part A is **BLOCKED** and no Japan transcription/ratification happened this session. The
blind dual-entry protocol is staged in `data/coercive-cases/drafts/ktab-japan-2017-scaffold.json`
(differing column order Influence | Position | Salience; Exercised Power = Influence × Salience / 100
checksum) and runs the moment the PDF lands. Part B (the paper scaffold) proceeded unconditionally.

### D14.1 — `schelling paper-evidence`: numbers regenerated from artifacts, never hand-typed
The paper's evidence base is a generated artifact, not a hand-written one. `schelling paper-evidence`
(new command; `src/schelling/paper/evidence.py`) writes `paper/EVIDENCE.md` where **every number is
computed from the repo's own artifacts**, each row carrying its source path + provenance stamp (git
short hash of the source file, or the dataset SHA-256 prefix for data-derived numbers):
- replication median (9.530) — re-solved from the committed emission fixture;
- DEU MAE/RMSE per method, split-sample, oracle gap (−0.84), worst issues — a fresh `run_backtest`
  over the DEU data (pinned by SHA-256), byte-identical to BACKTEST.md by determinism;
- successor leaderboard + bootstrap CIs + the 140/105/106 split — a fresh `run_successor_search`;
- published-context table and the China blind-verification facts — read from BACKTEST.md / the case
  JSON; the four sealed US-Iran ledger medians — read from FORECASTS.md (records gitignored, so the
  SHA-256 commitments *are* the artifact); the test count — collected live.
No wall-clock timestamps are written, so the file regenerates byte-for-byte from the same repo state
and can be diffed forever. Numbers no artifact can source are emitted as **open questions**, never
guessed (with DEU data present there are none). Determinism verified: re-runs are byte-identical.

### D14.2 — Deterministic paper figures + the outline (stubs only, no prose)
The same command renders four byte-stable SVGs to `paper/figures/` from the computed records (integer
coordinates, no random, no timestamps): the DEU abs-error histogram, the challenge-vs-compromise
error comparison, the R1 leaderboard table, and the pre-registered 40/30/30 split diagram.
`paper/OUTLINE.md` is a bullet-level skeleton (title candidates + section stubs, **no flowing
prose**) whose every empirical claim points to an `EVIDENCE.md` E-tag or a figure. Guardrails hold
(item 6): the coercive verdict stays **PENDING**, the noise-floor ceiling claim stays **scoped** to
cooperative EU-legislative bargaining on the classic input set, and no number appears in the outline
that is not sourced in EVIDENCE.md.

## Session 15 — paper assembly

### D15.0 — Draft sections relocated to paper/, treated verbatim, with one sanctioned roadmap fix
The eleven approved draft sections arrived in `docs/papers/draft/`; they were relocated to
`paper/draft/` so all of our paper artifacts live under `paper/` (`docs/papers/` holds the *source*
PDFs we cite, not our manuscript). Relocation is a move, not an editorial change — the prose is
treated as approved verbatim. The **one** authorized textual change (item 5): the introduction's
roadmap sentence said "Section 7 the case-library protocol and ledger. Section 8 limitations.
Section 9 concludes," conflating two sections and leaving the tail off by one against the actual
files (07 case-library, 08 ledger, 09 limitations, 10 conclusion). Corrected to "Section 7 the
case-library protocol. Section 8 the commit-reveal ledger. Section 9 limitations. Section 10
concludes." Flagged here and in the session report.

### D15.1 — `schelling paper-assemble`: deterministic, idempotent draft assembly
New command (`src/schelling/paper/assemble.py`) concatenates `paper/draft/00…10` in order into
`paper/DRAFT.md`, resolves every `[E-tag]` citation **inline to its EVIDENCE.md value with a
provenance footnote** (`(351)[^ev-E-DEU-N]`, footnote → value · source · provenance), places the four
figures at their section anchors (the two error figures after §3, the two successor figures after
§4 — the drafts carry no explicit anchors), and appends the `paper/BIBLIOGRAPHY.md` skeleton. A bare
family tag (e.g. `[E-LEDGER]`) resolves to its `E-LEDGER-*` members joined. Pure function of the
on-disk inputs (no wall-clock, sorted files, stable dict order) → byte-identical `DRAFT.md` every run.
Any tag EVIDENCE.md cannot resolve becomes a visible `**TODO(E-tag)**` in the text and is reported —
never a silent value. On the current repo: 0 TODOs.

### D15.2 — Six new evidence tags, each artifact-sourced
The drafts cite tags EVIDENCE.md did not yet cover; all six are wired into `schelling paper-evidence`
and sourced from a repo artifact (never hand-typed): `E-DEU-MAE-r1` (28.31) and `E-BASE-WMEAN-r1`
(23.64) — the handicapped round-1 evaluation, computed by a **second** `run_backtest` in equal-
capability / no-reference-point mode (Session 9's configuration); `E-METHOD-capabilities` — the
sourced treaty-regime capability table (points to `capability.py`); `E-CTX-bdm2011` and
`E-CTX-achen2006` — the published-context finding, parsed from BACKTEST.md; `E-WORST` — the worst-
issue aggregate, from the backtest record. The bibliography skeleton (`paper/BIBLIOGRAPHY.md`) adds
stubs for Feder 1987, Scholz–Calbert–Smith 2011, Thomson et al. 2006, Achen 2006, Bueno de Mesquita
2011, Meehl 1954, Dawes 1979, Tetlock 2005, Green & Armstrong 2007 (plus Arregui & Perarnaud 2021,
the DEU III dataset the paper actually evaluates on).

### D15.3 — Title finalized
The paper's title is finalized as **"Structure, Not Magic: An Open Replication and Predictability
Ceiling for the Bueno de Mesquita Forecasting Model."** The "title candidate (not finalized)" comment
in `paper/draft/00-abstract.md` is replaced by this title as the manuscript's H1; the decision is
recorded in `paper/OUTLINE.md`'s title-candidates block (chosen; the others struck through);
`paper/DRAFT.md` regenerated to carry it.

## Session 16 — references

### D16.1 — §6 citation correction + verified bibliography
The §6 "game-theorists vs unaided-judgement" finding is Green's sole-authored IJF studies, so
`06-reinterpretation.md` now cites **(Green 2002; 2005)** in place of the incorrect "(Green and
Armstrong 2007)"; the Green & Armstrong 2007 stub is removed. `paper/BIBLIOGRAPHY.md` is replaced
with verified full citations, and the **three `[VERIFY]` fields were resolved against the sources**
(no TODOs): Achen (2006) Ch. 10 = pp. **264–298** (Cambridge core); Bueno de Mesquita (2011) =
CMPS 28(1): **65–87**, doi:**10.1177/0738894210388127**; Feder (1987) = *Studies in Intelligence*
31(1): **41–57**, with the 1995 Westerfield reprint (pp. 274–292) noted. **One correction flagged:**
the requested Scholz citation ("Scholz, JG.J., & Smith, G.A.") dropped co-author **Calbert** and
garbled the initials; the verified form **Scholz, J.B., Calbert, G.J., & Smith, G.A.** (JTP 23(4):
510–531, doi:10.1177/0951629811418142) is used instead. Added Arregui & Perarnaud (2022) journal
citation with the 2021 data-deposit DOI kept separate.

### D16.2 — Assembler duplicate-number suppression
`schelling paper-assemble` no longer echoes a value in parentheses when it merely confirms a number
already written in the same sentence's prose: a single-tag citation whose value appears in the
current sentence resolves **footnote-only** (e.g. "…comprises 351 scoreable issues[^ev-E-DEU-N]"
rather than "…issues (351)[^ev-E-DEU-N]"); multi-tag citations and values absent from the prose keep
the parenthetical. Sentence detection ignores abbreviation dots ("et al. 2006") so the window is not
truncated mid-citation. Still deterministic + idempotent.

## Session 17 — integrity hardening

### D17.1 — Pre-registered grading rubrics; seal refuses a rubric-less forecast
A sealed forecast that cannot be graded by a rule fixed before resolution is a liability, so the
question schema gains a `ResolutionRubric` block (`schemas/question.py`): the **binary resolution
criterion**, the **adjudicating sources**, the **mapping rule** from real-world outcome to the 0–100
settlement continuum, and the **grading formula**. It is *grading metadata, not a solver input* — so
it is **excluded from `inputs_hash`** (`mc.monte_carlo.inputs_hash` dumps the game with
`exclude={"resolution_rubric"}`): adding a rubric never changes a forecast or a run's content-address,
and the four records sealed before the rubric existed keep byte-stable hashes. `schelling seal` now
**refuses to seal** a forecast whose question carries no rubric (checked *after* the idempotency
check, so already-sealed records re-seal harmlessly). `GRADING-Q-2026-USIRAN-STAGE2.md` is written
now, ahead of the 2026-08-31 resolution, and referenced from FORECASTS.md.

### D17.2 — External time-anchoring via OpenTimestamps
On every seal, `schelling seal` timestamps the ledger with the OpenTimestamps `ots` client
(`ledger.stamp_ledger`), storing the Bitcoin-anchored proof in `ledger-proofs/`, content-addressed by
the ledger's SHA-256 (`FORECASTS.md-<sha12>.ots`). A Bitcoin timestamp cannot be backdated — not even
by us — closing the "we could have written the commitment later" gap that a git history alone leaves
open. Missing `ots` tool or any failure is a **soft no-op with a warning**: the seal still succeeds
and the SHA-256 commitment stands. Proofs are committed as the audit trail; verification path
(`ots upgrade` / `ots verify`) documented in FORECASTS.md and `ledger-proofs/README.md`.

### D17.3 — `schelling verify <record.json>`: the one-command outsider audit
`backtest/verify.py` + the `verify` command run three checks and report PASS/FAIL each: **ledger-match**
(the record file's SHA-256 appears in FORECASTS.md — this exact artifact is the sealed one),
**inputs-hash** (recomputing the canonical game+config hash reproduces the stored `inputs_hash`), and
**determinism** (re-solving the embedded game with the record's own config + seed reproduces the
ensemble byte-for-byte, rule 2). Exits non-zero if any check fails — the audit an outsider runs
without trusting us.

### D17.4 — Grading rubric ratified with edits (final pre-registration)
Hassan ratified the Q-2026-USIRAN-STAGE2 rubric with edits (2026-07-22, pre-resolution), applied to
`GRADING-Q-2026-USIRAN-STAGE2.md` and its embedded machine-readable `resolution_rubric` JSON block:
the mapping bands now **tile 0–100 completely** (seven bands, adding explicit largely-US-terms 31–44
and largely-Iranian-leaning 61–69 interim tiers between the balanced 45–60 and the poles); a
**midpoint-default** rule (within a band the grade is the band midpoint unless the justification cites
specific settlement terms); a **canonical-text precedence** clause (the sealed game's continuum text
governs where the summary anchors differ); the binary criterion now pins the phase "as defined by the
17 June MOU's staged structure"; and the grading formula's final sentence now reads "The comparison
metric is |median − actual| per record; the grade integer, its justification, and all cited sources
are published in FORECASTS.md at grading." **This is the canonical embedded rubric** for the four
already-sealed US-Iran records: embedding it in the sealed game itself would change the record bytes
and break the seal (the rubric is part of the record's game but excluded from `inputs_hash`), so it
lives in this committed pre-registration and validates against `ResolutionRubric`. The bands were
checked to tile [0,100] with no gaps or overlaps. **Final — no edits under any circumstances after
2026-08-31.** `opentimestamps-client` was added as a project dependency (`uv add`) so `ots` is
available for D17.2 anchoring; the seal/stamp tests are monkeypatched to stay network-free.

## Session 18 — project audit (read-only)

### D18.0 — The honest state of Schelling, audited
A read-only audit (built/fixed/refactored nothing) recorded in
[docs/AUDIT-2026-07.md](docs/AUDIT-2026-07.md), every claim cited to an artifact. Headlines: 279
tests pass fresh (0 skipped, 41 s); 11 of 13 CLI surfaces exercised working (analyze/formalize need a
live API key, not run); all seven pre-registered gates restated with verdicts (replication passes;
Session-9, fair-fight, and both R1 candidates fail; oracle gap −0.84), pre-registration git-proven
(`3294081` before `8ea92b0`); every manuscript science number regenerates byte-identically (only the
live test count 267→279 and four provenance hashes drift, so `paper/EVIDENCE.md` is mildly stale).
**Two integrity headlines:** the v1-challenge sealed record **fails `schelling verify`** (stored
`inputs_hash` drifted from its embedded game; bytes + forecast still reproduce), and the real
`FORECASTS.md` ledger **has no OpenTimestamps proof** (`ledger-proofs/` holds only its README; the
seals predate the OTS feature). Grading rubric confirmed committed, schema-valid, band-tiling
complete, and dated pre-resolution. Overall grade 7.5/10; top three fixes: clean the integrity
apparatus (verify 4/4 + real proof), build the coercive library to 8 cases, grade the ledger at
2026-09-01 and regenerate EVIDENCE.md. Nothing else changed.

### D18.1 — Epoch-aware content-addressing; the v1-challenge cause (bisected, confirmed)
The audit found the v1-challenge sealed record failing `verify` on its inputs-hash. **Cause, bisected
and confirmed:** the record's stored `solver_config` has **no `reference_point` key** — it was created
before that field existed (Session 10, D10.4) — so its stored `inputs_hash` (`45d931c6cd91…`) predates
the field entering the canonicalization; dropping `reference_point` from a current-rules recompute
reproduces `45d931c6cd91` byte-for-byte, and adding it back gives `2cbb0bc624f3…`. `inputs_hash` now
takes a `hash_version` (`v2` current, `v1` pre-reference-point); `verify` tries each epoch newest-first
and, if none reproduces the label, reports **PASS-with-note** ("authenticated by determinism +
ledger-match"), never FAIL — a legacy record is never punished for a canonicalization change made after
it was sealed, and no sealed byte is ever touched. Regression tests pin all four records to 4/4 and
prove an unrecognized future epoch cannot re-break them. Mapping documented in FORECASTS.md.

### D18.2 — The real ledger is externally anchored; `schelling stamp`
The committed `FORECASTS.md` is now anchored with OpenTimestamps (proof in `ledger-proofs/`,
content-addressed by the ledger's SHA-256). A new `schelling stamp` command re-anchors the ledger any
time without a new seal. FORECASTS.md carries an honest correction-on-top note stating both facts
plainly: the seal *dates* (2026-07-21) rest on git history, while the external Bitcoin anchor dates
from **2026-07-22** (the day the feature existed) — still before the 2026-08-31 resolution, but not
back-dated to the seal.

### D18.3 — Evidence-drift CI gate (`paper-evidence --check`)
`paper-evidence --check` regenerates the evidence in memory and compares to the committed
`paper/EVIDENCE.md`: it **fails the build on any science-number drift** and only **warns** on
provenance-hash or test-count drift. Added to CI. DEU-derived tags are skipped when the (gitignored)
dataset is absent, so the CI gate never false-fails; those numbers stay guarded by the data-gated
local tests. `paper/EVIDENCE.md` regenerated at HEAD (test count 267 → 297; every science number
byte-identical).

### D18.4 — BACKTEST.md section ownership
`backtest` and `successor` are now section-aware: `backtest` owns the report body and preserves the
`<!-- LEADERBOARD -->` block that `successor` owns, so running one command never strips the other's
section (previously a bare `backtest` deleted the R1 leaderboard). BACKTEST.md regenerated; its stale
embedded engine SHA was refreshed (`0b979564c190` → current) and all MAE numbers are unchanged.

### D18.5 — Housekeeping
The empty `calibrate/` stub package is deleted (it returns post-September as a real module). The
CLAUDE.md §5 mypy-scope sentence is corrected to match reality: mypy runs `--strict` **globally**
across the package, not only on `src/schelling/solver`. (Item 6 dossier correction is a no-op —
`docs/DOSSIER.md` does not exist in the repo.)

## Session 19 — canon ingestion

### D19.0 — The canon joins the concepts corpus (classification fuel only)
Hassan's `CANON.md` (28 validated conflict-science concept cards, families A–E, each with an evidence
tag + coding rule + candidate-term flag) is placed at `data/concepts/canon.md` — a committed,
redistributable concept corpus, distinct from the gitignored lecture transcripts. A card-aware
chunker (`chunk_concept_cards`, split on the `**X#. Title (cites).**` bold markers, DOTALL so a
wrapped citation list keeps the card whole) turns each card into one retrievable chunk with a
`Canon <code>: <title>` citation ref; `KnowledgeIndex.build_from_corpus` (wired into `schelling
knowledge build --concepts`) indexes transcripts + concept cards together. The rebuilt index holds 98
chunks (70 transcript + 28 canon).

**Firewall verified both directions (no firewall code change — its whitelist is `templates.yaml`
only, so canon phrases stay catchable as leaks):** (a) all existing planted-fact leak tests stay
green; (b) a distinctive canon phrase ("loss-domain risk seeking", card A3) in an actor's **evidence**
field trips the leak detector, while the same concept citing the canon in **template_classification**
(excluded from the factual scan) passes; (c) the canon's theorist surnames (Kahneman, Tversky,
Fearon, Bueno de Mesquita, …) do not false-positive — single tokens are not distinctive 4-grams.

**Retrieval confirmed (bge-m3):** "why do weak actors win" → **Canon A1 (Interest asymmetry)** #1;
"settlement enforcement" → **Canon D1 (Third-party guarantees)** #1; "sacred stakes" → **Canon D2
(Indivisibility and sacred stakes)** #1.

**Scope discipline:** no solver changes, no model terms wired in — the canon is classification and
formalizer-guidance fuel only until the model-three spec selects candidate terms from it. The card
"Model term / Candidate term" annotations are documentation, not code. 305 tests green.

## Session 20 — Model Three (Asabiyyah, MT-1.0), sealed before its exam

### D20.0 — Pre-registration: specs/MT-1.0.md committed before the coercive library exists
`specs/MT-1.0.md` (working name **Asabiyyah**, the one text change from the approved drop-off) is
committed verbatim as the pre-registration — its git timestamp precedes any coercive case entering the
library beyond the current two. Every parameter is fixed now and may never be fitted, tuned, or
revised; any change is MT-1.1, reported separately. The model is scored **once**, at the 8-verified-
case coercive reading, alongside challenge / compromise / each source's published forecast.

### D20.1 — Implementation of `--solver model-three`, faithful to §3
`backtest/model_three.py` implements the §3 pipeline exactly and in order: (1) loss intensity
s←min(100, s×1.15) for L=1; (2) comfort decay s←s×0.80 for comfortable actors at T≥18 (hardened never
decay); (3) cohesion c←c×{0.85,1.00,1.15}; (4) WM′ = Σp·c·s / Σc·s over the adjusted values; (5)
status-quo pull λ = min(0.40, 0.25·[V=1∧G=0] + 0.15·[trap]), trap active iff the materially stronger
principal codes ledger and the weaker lens, prediction (1−λ)·WM′+λ·rp, with the no-rp fallback →
WM′. Every constant lives in one frozen `MTConstants` block quoting the spec's literals; a test
asserts the code's constants appear in `specs/MT-1.0.md` and equal the code
character-for-character. Wired into the coercive harness (`_forecast`, opt-in `head_to_head(methods=)`)
and `schelling coercive --solver model-three`, which **refuses to run until the 8-verified-case
reading** (specs/MT-1.0.md §6) — so the model is never run against the real library before then.

### D20.2 — §5 coding-flag schema, README, and coding sheet
The case-library schema gains an optional `coding_flags` block: per actor cohesion (h) / endurance
(e) / loss (L) / perception (m); per case horizon_months (T) / vulnerability (V) / guarantor (G);
`reference_point` (rp) already existed. Each flag carries a `{value, citation}`; the §5
ambiguity-default rule (h→baseline, e→comfortable, L→0, m→none; V→0, G→0, T omitted) is applied by the
loader for any absent flag. Flags are coded ex ante, blind dual-entry, and **sealed with the case's
verification before any model run**. `data/coercive-cases/README.md` documents the block and carries a
coding-sheet template. No case's flags were coded this session (that is a separate ratified step).

### D20.3 — Golden tests + the pre-registered BACKTEST.md row
Golden tests on synthetic fixtures cover every term firing alone and composed against an independent
hand-computation of §3 (the trap-active no-guarantor case shows λ=0.40 capped), plus determinism, the
constants-vs-spec check, and the coercive-harness integration; the existing suite stays green (321
total). MT-1.0 is added to BACKTEST.md's coercive section as **"PRE-REGISTERED — awaiting the
reading"** with the §6 gate quoted verbatim (generated in `writeup.py` so it survives regeneration).
The model is NOT run against the real library — scored once, at the reading, never before.

### D21.0 — Canon card C7 (intelligence asymmetry and decapitation) added to Family C
`data/concepts/canon.md` gains card **C7. Intelligence asymmetry and decapitation** (Wohlstetter
1962; Betts 1982; Jordan 2009, 2014; Johnston 2012), appended in Family C after C6. Tag: SUPPORTED
(asymmetry channels) / CONTESTED (decapitation effectiveness). Its three channels are scoped exactly
as written: operational reach stays priced into demonstrated capability (**never a separate
multiplier**); surprise vulnerability routes to C6 (range widening); and the information-advantage
channel is a **registered MT-1.1 candidate, considered only after the MT-1.0 reading** — nothing is
wired into any model now. The knowledge index rebuilt to 99 chunks (70 transcript + 29 canon); C7 is
retrievable (top hit for intelligence-advantage/decapitation queries). Firewall unchanged and green —
its whitelist is `templates.yaml` only, so C7's phrases stay catchable as leaks and its new theorist
names (Jordan, Johnston) do not false-positive. Card-count tests updated 28 → 29. 321 tests green.

### D21.1 — One-ply response preview (item 1)
For each top recommended move, `response_preview` (in `advise/strategy.py`) reports the move's
un-countered **gross** benefit and the **net** benefit after the most-affected opponent's best single
counter-response. "Most-affected" is defined operationally: we let *every* opponent take its
adversarial best response (the one that maximizes the settlement's distance from the advisor's ideal,
objective `-|s - ideal|`) and pick the opponent whose response leaves the advisor worst off (minimal
net). Net can never exceed gross (the opponent always has "do nothing" available), which is asserted in
the tests. **Interpretive choice, logged:** the paper gives no one-ply-response construction — this is
our own decision-analytic overlay on the compromise settlement, not a Scholz/BdM equation. Under the
exact (compromise) lens the response is a closed form on the weighted mean; under the challenge lens it
is simulated at reduced draws and flagged `simulated=True` (the report/CLI print "(sim)").

### D21.2 — `--mode equilibrium` (exact lens only, item 2)
`equilibrium_exact` iterates best responses across all actors (each moves its position within its
stated range and salience within bounds toward its **own** ideal, objective `|s - ideal|`) to a fixed
point, capped at 25 iterations. A fixed point (no actor changes) is reported `converged=True`; a
settlement value that recurs in the path is reported honestly as a `cycle` (closed on itself) rather
than a false convergence; hitting the cap without either is `converged=False, cycle=[]`. The output
carries the settled settlement, each actor's equilibrium move (position/salience from→to), and the full
convergence path. Equilibrium is **exact-lens only** — the simulated challenge lens has no closed form
to iterate cheaply; the CLI refuses `--mode equilibrium --solver challenge` with a friendly error. In
this mode the standing one-sided caveat is replaced by the **successor caveat**: "assumes model-optimal
play by all actors — an upper bound on adaptation, not a prophecy" (`SUCCESSOR_CAVEAT`). **Interpretive
choice, logged:** best-response-toward-own-ideal is our reading; the paper models a single expected
settlement, not an iterated-best-response dynamic. On the monotone weighted-mean dynamics used here the
process converges in practice (actors walk to their range bounds), so the cycle branch is defensive.

### D21.3 — Robustness grading across the MC draws (item 3)
Every recommended move's (and top-3 target's) benefit is recomputed across the Monte-Carlo draws:
`robustness_exact` samples the triangular inputs with `sample_game`/`derive_rng` and evaluates the
closed-form benefit per draw; `robustness_challenge` uses paired `run_monte_carlo` median distributions
(baseline vs moved, same seed). `_grade` reports the p10/p90 benefit CI and the **sign-stable
fraction** (share of draws whose benefit shares the point estimate's sign), grading **ROBUST** when
≥ 0.90 else **KNIFE-EDGE**. Applies to both lenses. This is pure Monte-Carlo bookkeeping over the
deterministic solver — no LLM, no estimate (rules 1–2).

### D21.4 — Move vocabulary v1 (item 4) + the deferred flag-based moves
`advise/moves.yaml` maps named diplomatic actions to typed parameter deltas: `phased_concession`
(position → settlement), `escalate_commitment` / `deescalate_signal` (own salience ±),
`coalition_pull(target)` (target position → advisor), `side_payment` (target salience −), each with a
one-line rationale; `advise/moves.py` resolves a move to a concrete `(field, value, MoveAction)` clamped
to the actor's stated range. The vocabulary is extended by editing the YAML. `advise` searches over
vocabulary moves alongside the sweep and renders recommendations as named actions with their deltas.
**Explicitly deferred (item 4, logged here and in the YAML header): flag-based moves through MT-1.0
mechanics — `guarantor`, `trap`, and the cohesion/endurance levers — are NOT in the vocabulary.**
Advice may not use an unscored model: MT-1.0 is scored once, at the pre-registered 8-verified-case
reading (D20.0), and until then no recommendation may turn a knob only MT-1.0 prices. These moves
return only after that reading. A test asserts the vocabulary is disjoint from `{guarantor, trap,
cohesion, endurance}`.

### D21.5 — Package search (item 5, exact lens only)
`package_search` exhaustively evaluates the best two-move bundles over the vocabulary + sweep moves at a
coarse grid (position/salience step doubled), keeping benefit and cost separated as always and grading
each bundle's robustness. Bundles are returned best-benefit-first. Exact-lens only (the exhaustive
closed-form evaluation is cheap; the simulated lens is not).

### D21.6 — Strategy brief + report/CLI surfaces (item 6)
`strategy_brief` emits one deterministic, readable paragraph per advised actor — best own move (as an
action), its net-after-response, robustness grade, best persuasion target, and the equilibrium picture
when computed. The report (`report/render.py`) gains guarded sections — response preview & robustness,
best two-move packages, equilibrium, and the strategy brief — all behind presence checks so the
pre-2.0 `advise.json` golden renders **byte-identically** (its records carry none of the new fields);
the successor caveat swaps in only when `record.mode == "equilibrium"`. New goldens
(`advise_strategy.json/.html`) cover every new render path; determinism is pinned with a byte-identical
re-run test. All new advise fields are optional/defaulted and `advise(strategy=False)` is the library
default, so Session-7 tests and goldens are untouched. **344 tests green.**

### D21.7 — Housekeeping: restored CI to green (pre-existing E501 from D20)
While gating this session I found `main` had been **red on CI since D20** (`uv run ruff check .`
failing): the Model Three work introduced 23 `E501` over-length lines (in `backtest/writeup.py`,
`backtest/verify.py`, `knowledge/chunker.py`, `knowledge/index.py`, `paper/assemble.py`,
`paper/evidence.py`, and five test files) that were merged red across D20 and D21.0, contra rule 5.
All were wrapped mechanically — string literals via adjacent-literal concatenation (byte-identical
output, so `paper-evidence --check` and every golden are unaffected) and comments/dividers by
re-wrapping. No behaviour changed. This restores the green-before-commit invariant.

### D21.8 — Housekeeping: made the transcript-dependent tests CI-hermetic
With ruff unblocked (D21.7), `pytest` ran on CI for the first time since D20 and surfaced **seven
pre-existing failures** — all environmental: the lecture transcripts under `data/transcripts/` are
gitignored (not redistributable), so on CI they are absent, and seven tests that assert on real
lecture content failed (`test_chunker::test_real_transcripts_yield_29_lectures` /
`::test_chunks_carry_lecture_provenance`; `test_knowledge::test_search_returns_chunks_with_refs` /
`::test_seeded_relevance_dating_game`; `test_templates::test_transcript_refs_are_real_lectures`;
`test_cli::test_knowledge_build_then_search` / `::test_knowledge_build_missing_extra_is_friendly`).
These had been red on CI latently — the ruff failure short-circuited the job before pytest ran, so
nobody saw them; "N tests green" in prior sessions was always the **local** count (Hassan's env has
the transcripts). Each was guarded with the project's established idiom —
`@pytest.mark.skipif(not _HAS_TRANSCRIPTS, ...)`, matching the seven existing `skipif(not
<data>.exists())` guards for the gitignored DEU/ICB data — where
`_HAS_TRANSCRIPTS = TRANSCRIPTS.exists() and any(TRANSCRIPTS.glob("*.txt"))`. Locally (transcripts
present) all seven still run and pass; on CI they skip. No production code touched. CI now runs the
full gate green for the first time since D20.

### D22.0 — Second sealed-ledger question pre-registered: Q-2026-IAEA-SEP (IAEA Board vote)
A second sealed-ledger question on the same underlying conflict, deliberately in a **different game
and different domain** from the coercive Q-2026-USIRAN-STAGE2 bilateral bargain: what the IAEA Board
of Governors (35 members) decides to do about Iran at its September 2026 meeting — a multilateral
committee vote, i.e. the **DEU family**, the one domain where the compromise model is validated to
the extractable-signal ceiling (Sessions 9-11). Sealing both tests the machine where its evidence is
strongest (committee voting) and where it has none (coercion), on one conflict; a divergence between
the two forecasts is then diagnostic rather than noise (the shared-failure-mode caveat is stated in
the question package, on the record before any forecast exists). **Pre-registration made public:**
`GRADING-Q-2026-IAEA-SEP.md` (the rubric — 7 bands tiling 0-100, canonical-text clause, midpoint
default, `schelling verify` + `ots verify` integrity checks; header stamped pre-registered 2026-07-22
before the 2026-09-30 resolution, awaiting Hassan's ratification, final after 2026-09-30) and
`docs/questions/question-iaea-sep.md` (the approved question package + rationale) are **committed** —
the pre-registration must not sit in gitignored `analyses/`. Resolution 2026-09-30 23:59 UTC, grading
2026-10-05. The situation text (`analyses/iaea/situation.txt`) is the paste-ready block from the
package, de-indented, and stays gitignored.

### D22.1 — The IAEA formalize draft (live-searched; NOT solved, NOT sealed)
`schelling formalize analyses/iaea/situation.txt --search --max-searches 6 -o analyses/iaea/iaea.json`
produced the draft: `claude-opus-4-8`, 4 searches used, **35 sources fetched**, in=76,432 / out=12,465
tok, **$0.7338**, 0 retries; `frozen_at`/`live_searched` stamped today per rule 7 (a live question, not
a backtest). The draft models **7 actors** — `united_states` (pos 15/35/65, cap 100), `e3_uk_france_
germany` (25, cap 70), `western_aligned` (32, cap 62), `russia_china_niger` (72, cap 55),
`nonaligned_abstainers` (52, cap 68), `director_general_secretariat` (63, cap 60), and
`iran_subject_influence_only` (88, cap 45, off-Board influence only) — with 9 assumptions and per-value
evidence notes, all traced to the June 10 2026 Board vote (21-3-10) and the parallel US-Iran track.
Three formalizer choices flagged for Hassan's review: **(a) capability rule** — it did NOT use the
Board's one-member-one-vote rule; it chose a penholder/diplomatic-leverage weighting (US 100, E3 70,
down to the abstainer bloc), explicitly disclosed as a modelling choice not established by any source
(assumption 5) — arguably under-weights the 10-abstainer blocking numbers; **(b) bloc aggregation** —
only the four penholders and the three no-voters are source-grouped; the yes-voters→`western_aligned`
and abstainers→`nonaligned_abstainers` groupings, and folding Niger with Russia/China, are analyst
aggregations disclosed as assumptions 2-3; **(c) Iran** — included only as an off-Board influence
(not a voting member), preferred point near "close the file", magnitude inferred from its
cooperation-suspension law and June 2026 re-invite, per assumption 7. **STOP: not solved, not sealed —
the human review gate applies; Hassan reviews the draft with Claude before anything is solved** (per
the question package's workflow). `analyses/iaea/` stays gitignored.

### D22.2 — Band mapping: `RubricBand` + `report/bands.py` (the two-audience report, item 1)
`ResolutionRubric` gains an optional structured `bands: list[RubricBand]` (each an inclusive `[lo, hi]`
slice of the 0-100 continuum with its outcome label, verbatim). The whole rubric is already excluded
from `inputs_hash` (D17.1), so adding a field changes no forecast, no content-address, and no sealed
record. `report/bands.py` (`map_bands`) is pure, deterministic, LLM-free: it classifies every cached
MC draw (`outcome_distribution`) into the bands and returns per-band probabilities, the modal band,
and the band the ensemble median lands in. **Interpretive choices, logged:** (1) band membership uses
each band's `lo` as a **threshold** — a draw falls in the last band whose `lo` it clears — so float
draws partition [0,100] with no gaps even where the written integer ranges leave unit holes (0-9 then
10-24); (2) the **modal band** breaks ties by lowest index for determinism. A rubric with **no**
structured bands is treated as **arithmetic/linear** (the grading formula maps the outcome directly;
`kind=LINEAR`); **no rubric at all** returns `kind=NONE` — both carry a plain-language note so the
report can degrade gracefully and say so. Works identically for either solver's record.

### D22.3 — `sources_fetched` carried into the ForecastRecord (appendix provenance)
`FetchedSource` moved to core `schemas.forecast` (re-exported from `formalizer.schemas`, exactly as
`Assumption`/`DraftMetadata` were), and `ForecastRecord` gained `sources_fetched: list[FetchedSource]`
(optional, default `[]`). The solve paths (`build_forecast_record`/`forecast`, and the CLI's
`_load_solve_input` → solve/analyze) now carry a live-searched draft's sources into the record, so the
report's APPENDIX can list them. Additive and defaulted — existing records/goldens are unaffected.

### D22.4 — Position-to-words vocabulary in a committed YAML (item 4)
`report/position_words.yaml` maps a 0-100 position (and salience) to an auditable phrase, keyed to
continuum **thirds** (coarse) and **fifths** (fine); `report/vocab.py` loads it. The phrasing lives in
the YAML, never hardcoded in report strings, so it is editable and reviewable. Phrasing is generic and
direction-based ("toward the low end", "close to the midpoint") because the continuum's own
`anchor_0`/`anchor_100` text supplies the *meaning* of the ends; the vocabulary supplies the *location*.
Positions are 0-100 by contract (`schemas.stakeholders`), so the buckets are fixed thresholds.

### D22.5 — The two-audience layered report + rubric-presence dispatch (items 2, 3, 6)
`render_forecast_narrative` composes four sections in order — **VERDICT** (modal band in the rubric's
own words + its probability, the median and its band, and the single highest-swing parameter as "what
would change this"), **READING** (what 0/100 mean, each actor in a sentence with position-in-words, the
capability×salience weight arithmetic naming the heaviest actors + the closed-form compromise point,
and the 2-3 widest input ranges), **ANALYST BRIEF** (band-probability table; **both solvers side by
side** — this run's median+band vs the compromise closed-form point+band, with their disagreement
stated and **never blended**; full stakeholder table with evidence; inputs split **sourced** (actors
with evidence notes) vs **inferred** (the assumptions list); the tornado as "what to watch"; and
diagnostics incl. degenerate-lock + mode-vs-MC gap), and **APPENDIX** (sources fetched, inputs hash,
engine SHA, seed, and the exact reproduce command). **HARD CONSTRAINT met (item 3):** every line is
deterministic template text composed from record fields + the committed band/word vocabularies — no
LLM anywhere; a byte-identical re-run is tested. **Dispatch (item 5):** `render_forecast` routes a
record whose game carries a committed rubric to the narrative layout, and everything else to the
unchanged pre-D22 standard layout — so existing report goldens stay **byte-identical** (the forecast
golden has `resolution_rubric: None`). The narrative's extra CSS is injected via a defaulted
`_page(..., extra_css)` argument so no other report's stylesheet changes. The "both solvers" cross-check
is realized by computing the compromise weighted-mean point closed-form from the embedded game (a full
two-record pairing is a possible future enhancement). New fixture + golden (`forecast_narrative.json`
/ `.html`) and `tests/test_narrative.py` cover band arithmetic (sum-to-1 vs a hand-computed fixture),
modal/median bands, the linear and no-rubric graceful paths, verdict text, determinism, the dispatch
both ways, and the vocabulary. 359 tests green.

### D23.1 — Band-probability strip (SVG) in the VERDICT section
`svg.band_strip` renders one segment per rubric band, deterministic from the record + committed
rubric. **Interpretive choices, logged:** (1) segments are **threshold-tiled** — segment *i* spans
`[lo_i, lo_{i+1}]` (last to 100), matching the band-membership rule (D22.2) so the strip tiles 0-100
with no gaps and each segment covers exactly the region that maps to its band; (2) **fill opacity
encodes the draw share** (floor 0.12, cap 0.85 so a 0-share band stays visible and a modal band never
goes pure-solid); (3) the **modal band is outlined** (`modal_stroke`); (4) beneath the strip sit a
**median pointer** (a triangle at the median) and an **80%-CI bracket** from p10 to p90 — the shared
`_strip_footer`. Band labels are the rubric's own words, truncated to each segment's pixel width.
**Arithmetic/linear rubrics** (no bands) get `svg.density_strip` instead: a continuous density of the
draws across 0-100 (opacity ~ local density) with the identical pointer/bracket. The strip degrades
to nothing when there are no cached draws.

### D23.2 — Weighted actor diagram (SVG) in the READING section
`svg.weighted_actors` places each actor as a circle on the 0-100 line at its mode position, radius
`= r_min + (r_max - r_min)·sqrt(weight/max_weight)` with `weight = capability·salience` and a min
floor so tiny actors stay visible. Circles are **greedily packed into vertical rows** (sorted by
position, then name — deterministic) so none overlap. The settlement is a vertical line; **non-voting
/ out-of-body actors** get a dashed ring + a `*` on their label. **Interpretive choice, logged:** the
non-voting coding is a new `GameSpec.non_voting_actor_ids` (list of ids) — presentation metadata only,
so it is **excluded from `inputs_hash`** (added to the exclude set in `mc.inputs_hash` *and*
`advise._inputs_hash`), exactly like the rubric; a defaulted empty list leaves every existing/sealed
game's hash byte-identical (verified: advise + mc + integrity suites unchanged). If no actor is coded
non-voting, no flags are drawn (graceful).

### D23.3 — Both figures are pure functions; degrade gracefully
Each figure is a pure function of the record (+ rubric + palette): no LLM, no clock, byte-identical on
re-run (tested directly on the SVG string and via the full-report determinism test). Missing fields
degrade to a small placeholder or an omitted figure rather than an error (no draws -> no strip; no
actors -> "(no actors)"; no non-voting coding -> no flags).

### D23.4 — Colours from a committed palette map
`report/palette.yaml` holds the figure colours — **two ramps, one per continuum half** (`low_half`
amber for < 50, `high_half` teal for >= 50) plus `modal_stroke` / `median_pointer` / `ci_bracket` /
`non_voting_flag`. `report/palette.py::load_palette()` reads it into an `svg.Palette`; nothing is
hardcoded in `svg.py` or `render.py`. Each figure carries a one-line HTML legend beneath it (the
actor diagram names the two halves from the continuum's own `anchor_0`/`anchor_100`).

### D23.5 — Accessibility
`svg._svg` gained optional `title`/`desc`; both new figures pass `role="img"` with a `<title>`
(short name) and a `<desc>` — a one-sentence summary generated from the same record fields (e.g.
"Band-probability strip: {modal label} is the most likely outcome at {p}% of {n} draws; the median is
{m} of 100."). Both default to empty, so every pre-D23 figure renders byte-identically.

### D23.6 — Goldens updated intentionally
The narrative report golden (`forecast_narrative.{json,html}`) was regenerated to include the two new
figures; the fixture game gained a non-voting "subject" actor + `non_voting_actor_ids` to exercise the
flag. **Every other report golden (standard forecast, draft, advise, backtest) is unchanged** — the
figures live only in the narrative VERDICT/READING sections, and the new SVG text classes live in the
narrative-only `_NARR_CSS`. `tests/test_narrative.py` adds: strip shares equal the computed band
probabilities, segments tile 0-100, SVG byte-identical + accessible, the non-voting flag appears when
coded and not otherwise, the palette loads two ramps, linear rubrics use the density strip, and the
report stays offline-clean. 366 tests green; ruff/format/mypy clean; paper-evidence --check passes.

### D24.1 — Render-time rubric resolution from the committed grading file
The formalizer never writes a `resolution_rubric` into the game, so every solved record — including
the four **sealed US-Iran records that can never be regenerated** — embedded none, and the two-audience
narrative fell back to the standard layout. Confirmed empirically before changing anything (all ten
forecast records report `rubric=none`; a USIRAN record rendered the standard "Headline" layout, not
"Verdict/Reading"). Fix: `report/rubric_lookup.py` resolves a rubric at **render time** —
`grading_path` walks up from the record's directory (and the cwd) to find `GRADING-<question_id>.md`,
`parse_rubric_block` extracts the first ```json fenced block that validates as a `ResolutionRubric`.
The CLI `report` command's `_resolve_rubric` injects it into the **in-memory** copy of the record and
passes a source label to `render(..., rubric_source=...)`, which the appendix states ("resolved at
render time from GRADING-….md (the record was not modified)" vs "embedded in the record").
**Precedence: an embedded rubric always wins** — lookup only runs when the game has none.
**Read-only (item 2): the record file on disk is never rewritten** (asserted by test: bytes unchanged;
`schelling verify` on the sealed record still passes 4/4). The missing-rubric path (no rubric, no
grading file) is byte-identical to before.

### D24.2 — Structured `bands` added to both grading files' machine-readable blocks
For the band-probability strip the rubric needs structured `bands` (D22.2), which the pre-D22 grading
files lacked. **USIRAN:** its machine-readable block already existed but carried the seven bands only
in `outcome_mapping` prose; a `bands` array was added as a **verbatim structuring of those already-
committed bands** — same boundaries, same meaning — with an in-file note. This changes no grading
semantics (`outcome_mapping` and the sealed continuum text remain canonical), is done **pre-resolution**
(before 2026-08-31, when the rubric still allows ratified structuring), and is **hash-irrelevant** (the
rubric is excluded from `inputs_hash`) — so no sealed record's hash and no ledger/OTS seal is touched
(seals are on the record files and FORECASTS.md, not the grading file). **IAEA:** had no machine-
readable block at all (only a markdown table); a full `ResolutionRubric` JSON block with the seven
table bands was appended so `schelling report` can resolve it. **Flagged for Hassan:** the USIRAN grading
file is his ratified pre-registration; this edit is a faithful machine-readable structuring, not a
change of grading — please confirm at review.

### D24.3 — Rubric attached to the IAEA draft for future solves (hash-unchanged)
`analyses/iaea/iaea.json` (gitignored) gained `game.resolution_rubric` (the IAEA rubric with its seven
bands) plus `non_voting_actor_ids = ["iran_subject_influence_only"]` (Iran is the subject, not a
voter). Asserted by test that adding a rubric + non-voting coding leaves `inputs_hash` byte-identical
(both are hash-excluded), and confirmed directly: the draft's hash stays `a4aff64fd883…`, so a future
solve reproduces the same run_id and embeds the rubric (embedded then wins over lookup). Both target
reports re-rendered and verified: the **IAEA compromise** record (modal band "No new resolution; report
noted; left to the diplomatic track") and a **sealed US-Iran compromise** record (modal band "Interim
or framework on largely US terms") each show the band strip, actor diagram, verdict and reading
sections. New `tests/test_rubric_lookup.py` (12 tests: parse, walk-up lookup, embedded-wins precedence,
inject-without-rewrite, missing-rubric unchanged, determinism, source labels, hash-unchanged). The
narrative golden was updated for the new "Rubric source" appendix line. 378 tests green; ruff/format/
mypy clean; paper-evidence --check passes.

### D24.4 — US-Iran band structuring ratified; provenance hardened; drift-guarded
Hassan ratified the D24.2 band structuring. His verbatim ratification note now sits **beside the
`bands` array** in `GRADING-Q-2026-USIRAN-STAGE2.md` (and, dated, in the IAEA grading file): "Bands
array added 2026-07-22 as a structured restatement of the seven bands already committed in
outcome_mapping — identical boundaries and meaning, no semantic change, added so the report renders
the probability strip. The prose outcome_mapping and the sealed continuum text remain canonical; if
the array and the prose ever disagree, the prose governs. Pre-resolution; rubric is excluded from
inputs_hash so no sealed record, ledger entry, or timestamp is affected." A **drift-guard test**
(`test_committed_grading_bands_match_outcome_mapping_prose`, parametrized over both grading files)
asserts the structured `bands` boundaries exactly equal the boundaries stated in the `outcome_mapping`
prose (and that they tile 0-100 contiguously) — so the two representations can never silently diverge;
any future edit to one that does not match the other fails CI. **Confirmed:** all four sealed US-Iran
records still `schelling verify` 4/4 (ledger-match, inputs-hash, determinism), and `FORECASTS.md` +
`ledger-proofs/` are byte-untouched (the OTS-anchored ledger is unaffected — only the grading files
changed). Full gate green.

### D25.1 — Cap displayed band shares (never a false certainty)
A displayed probability share must never read 100% or 0%: `svg.format_share` renders ``>99%`` for any
share above 0.99 and ``<1%`` below 0.01, otherwise the rounded percent. Applied everywhere a share is
shown — the verdict line, the band-probability table, the strip labels, and the strip's `<desc>`.
Boundaries are exact-inclusive on the safe side: 0.99 -> "99%", 1.0 -> ">99%", 0.01 -> "1%",
0.0 -> "<1%". The converged-fraction diagnostic and `width="100%"` are not shares and are untouched.

### D25.2 — Standing scope line beneath every verdict
A fixed, deterministic sentence now sits beneath the verdict in every narrative report (banded,
arithmetic, or no-rubric): "These shares reflect uncertainty in the stated input ranges only. They
exclude model error, coding error, and events outside the modelled game." Template text, always shown.

### D25.3 — Per-actor short names (display only, hash-excluded)
`GameSpec.short_names: dict[str, str]` (actor id -> short name) joins `non_voting_actor_ids` as
display metadata **excluded from `inputs_hash`** (added to the exclude set in both `mc.inputs_hash` and
`advise._inputs_hash`); a defaulted empty dict leaves every existing and sealed hash byte-identical
(asserted by test; sealed records still verify 4/4). The report resolves each actor's short name as an
explicit override else `_derive_short(name)` = the first clause before the first parenthesis or
spaced/en/em dash (internal hyphens kept, e.g. "Non-aligned swing bloc"). **Prose and figures use the
short name; the stakeholder table keeps the full name.** The "what would change this" line and the
widest-uncertain-inputs list also use short names.

### D25.4 — Actor-diagram legend uses fixed direction phrases
The weighted-actor legend no longer truncates the continuum's anchor prose (which produced clipped,
ambiguous fragments); it now states fixed, direction-derived phrases: "Amber = the low half (toward 0);
teal = the high half (toward 100)."

### D25.5 — Grouped player sentences (less template monotony)
The READING "players and where they stand" list groups actors that share a side (position third) and
salience tier into one sentence — "Three members sit near the low end: A, B and C — a defining issue
for each" — instead of one identical sentence per actor. Singletons keep the direct form; the salience
phrase switches "for it" -> "for each" in a group. Deterministic (groups keyed on the vocab phrases,
first-appearance order). New `tests/test_narrative.py` cases cover the cap boundaries, the always-on
scope line, short-name derivation + override + prose/figure/table split, the fixed legend text, and
the grouping; sealed hashes confirmed untouched. 387 tests green; full gate + paper-evidence pass.

### D26.1 — `schelling dossier`: a researcher-grade document from a record
New command `schelling dossier <record.json> [--advise-records …] [--pdf] [--no-narrative]` assembles a
dossier from a forecast record plus, when present, its advise records, analog panel, and grading
rubric (resolved read-only from the grading file as in D24.1 — the record is never modified). HTML by
default; PDF with `--pdf`. Package `src/schelling/dossier/` (assemble/narrative/pdf).

### D26.2 — The HARD WALL: COMPUTED vs NARRATIVE, with tag resolution
COMPUTED sections (verdict + band strip, formal game table with evidence, assumptions split, the
distribution + both solvers, diagnostics, strategy tables from advise records, analog base rates,
sensitivity, provenance appendix) are deterministic template text from the existing renderer. The five
NARRATIVE sections (history, present state, interpretation, enforceability, limitations) are ONE
tightly-constrained LLM call: the model writes ``{{tags}}`` for every model quantity and the assembler
resolves them from the record — it may never emit a bare numeral for a model quantity. `validate_narrative`
rejects a generation with (a) an unresolved tag, (b) an invented model numeral (a percent other than the
fixed 80% CI level, or a model term glued to a number), or (c) a concept-library leak (new firewall
`scan_text`, the text-level counterpart of `find_leaks`); `generate_narrative` retries with a correction
up to a cap, then raises `NarrativeRejectedError`. Every factual world-claim must cite a fetched source;
the concepts firewall applies unchanged. Replayable via any `LLMClient` (tested with `ReplayClient`).

### D26.3 — Section order + the record as sole provenance
Thirteen sections in the fixed order (Executive verdict · Question and scale · How we got here · Present
state · The formal game · The forecast · Why this outcome · Strategy by actor · Enforceability and
compliance [canon C8/D1/D5, ANALYSIS ONLY] · Historical analogs · What would change this · Limitations ·
Provenance appendix). `record_context` derives the narrative's situation + sources FROM the record
(continuum, notes, actor evidence, assumptions, sources_fetched) — self-contained, and the only
provenance the narrative may cite.

### D26.4 — Determinism and disclosure
COMPUTED sections + `--no-narrative` are byte-identical on re-run (tested). The narrative is not
deterministic — the dossier records its SHA-256, model, and cost in the appendix and states in the
document that narrative sections are model-written and source-cited while every figure is computed;
`--no-narrative` yields a fully deterministic dossier (placeholder in the narrative slots).

### D26.5 — PDF
`--pdf` renders via WeasyPrint (lazy-imported, optional — NOT added to the synced extras, so CI never
installs it and the PDF test skips cleanly). The dossier carries `@page` CSS: A4, page numbers, a
running header (question id · freeze date via a `string-set` off-screen element), figures inline,
appendix last. A missing WeasyPrint gives a friendly error, not a traceback.

### D26.6 — Tests
`tests/test_dossier.py`: tag resolution + unresolved-tag failure, numeral rejection (incl. the CI-level
exception), narrative retry-then-accept and reject-after-cap, the firewall leak rejection, section
order, computed-section + fixed-narrative determinism, `--no-narrative` mode, advise-record integration,
the read-only guarantee (CLI never rewrites the record), the api-key guard, and a gated PDF build. All
dossier tests pass; sealed hashes are untouched (the dossier never hashes or writes a record).

### D26.7 — Restore green: scope the paper's `E-LEDGER` evidence to its one question
An out-of-band commit (`c1b27bc`, "Seal Q-2026-IAEA-SEP v1") added IAEA rows to the FORECASTS.md
ledger and turned `main` red: `paper.evidence._ledger_items` tagged rows `E-LEDGER-{model}-{vintage}`
without the question id, so IAEA's `challenge v1` (45.837) collided with US-Iran's (34.576) and both
overwrote the paper's figures (breaking `test_paper` and the evidence-drift check). The paper is
explicitly about **one** live question — US-Iran stage two ("four forecasts on one ongoing
geopolitical question", §8) — so `_ledger_items` now scopes its `E-LEDGER-*` evidence to
`_PAPER_LEDGER_QUESTION = Q-2026-USIRAN-STAGE2`. IAEA and any later-sealed question remain real ledger
entries in FORECASTS.md but are not this paper's evidence. **The frozen paper, EVIDENCE.md, and the
four sealed US-Iran figures are byte-unchanged**; the test and `paper-evidence --check` pass again
(only pre-existing provenance/test-count warnings remain). Ratified by Hassan ("Fix ledger, then
merge"). Sealed records and the ledger itself are untouched.

### D26.8 — Enforceability disclaimer written for the reader
The enforceability section's closing disclaimer echoed internal guardrail wording ("never a defection
playbook") and canon codes (C8/D1/D5) — model-facing framing, not reader-facing. Replaced with one
plain sentence that keeps the substantive point: "This section is an analysis of how durable the
resulting agreement is likely to be — an analysis of coalition durability, not a prescription." The
model-facing guardrail stays in the narrative system prompt (where it belongs); only the reader-shown
line changed. A test asserts the disclaimer carries no guardrail wording or canon codes.

### D27.1 — `schelling llm-forecast`: the direct-judgment baseline
New command `schelling llm-forecast <game-or-draft.json>` gives a model the SAME situation text,
sources, and 0-100 continuum the solver received and asks directly for a settlement point, an 80%
interval, and (when the rubric is banded) a probability per band — **no solver, no game math**
(`src/schelling/llm_forecast/forecast.py`). It samples `n=5` independently (via `LLMClient.complete`,
which gained an optional `temperature` that elicits a sampled judgment instead of adaptive thinking);
the headline is the **median** of the sampled points and the **spread** (max-min) is its
self-consistency. The rubric is resolved read-only from the grading file if absent (D24.1), so band
probabilities can be requested. Replayable via any `LLMClient` (tested with `ReplayClient`; CI never
calls the live API).

### D27.2 — `LLMForecastRecord` with full provenance; SHA-256 is the commitment
`LLMForecastRecord` (schemas/forecast.py) carries the judge model, temperature, n_samples, prompt
hash, every sample verbatim (`LLMSample`: point / p10 / p90 / band probs / raw text), cost, and the
aggregate `ensemble`. **Non-deterministic by nature** — re-running produces different samples — so
there is no reproducibility claim; the commitment is the SHA-256 of the record file (as
`schelling seal` computes). `render_llm_forecast` + the CLI output state this plainly.

### D27.3 — Sealable, unchanged, labelled `llm-judgment`
The record is shaped so `schelling seal` accepts it with **no changes**: `model = "llm-judgment"`
labels the ledger row, `ensemble.median` is the sealed headline, and an embedded `game` supplies the
frozen date and the `resolution_rubric` the seal requires (a judgment that cannot be graded by a
pre-registered rule is not sealed). Verified: sealing an llm record writes a `| llm-judgment | …` row.

### D27.4 — Pre-registered comparison, fixed now, with a refuse-to-rank guard
`schelling compare` computes `|median - actual|` across challenge, compromise, and llm-judgment on the
live ledger (`src/schelling/llm_forecast/compare.py`). **Exploratory until `MIN_GRADED = 10` graded
questions** (with all three families sealed): the harness returns no ranking and prints only the
exploratory status before the threshold — the same discipline the coercive reading holds to (D20).
Only at 10+ does it rank by MAE. Fixed now, before any question grades.

### D27.5 — Contamination rule; the live sealed ledger is the clean venue
An `llm-forecast` run whose inputs resemble DEU or the coercive library is auto-flagged
`CONTAMINATION-RISK` (`detect_contamination`, overridable with `--contamination-risk/--live-question`)
and reported separately, because the model may know those historical outcomes. `docs/LLM-BASELINE.md`
states that the live sealed ledger — questions sealed before they resolve — is the clean venue, and it
is the only venue `schelling compare` ranks over (contaminated runs never reach it). `tests/
test_llm_forecast.py`: sampling/aggregation, record shape + round-trip, parse rejection, contamination
flag + override, the refuse-to-rank guard both sides of the threshold, the seal path, the
non-determinism note, and the replayed CLI. 413 tests green; sealed records + the ledger untouched.

### D28.0 — Question-design lesson: site status-quo outcomes at a pole, not the midpoint
Pre-resolution observation on Q-2026-IAEA-SEP (recorded 2026-07-23, an analyst note that changes no
grading rule — see the note added to `GRADING-Q-2026-IAEA-SEP.md`): this continuum places the
**no-action / status-quo** outcome at its **midpoint** (band 40-59). A mean-based solver (the
compromise weighted mean, and to a degree the challenge median) lands mid-scale *mechanically* when
actors are dispersed across the scale, so a placement in the midpoint band may reflect **continuum
geometry rather than a genuine belief about inaction** — the two are confounded when the status quo
sits at the centre. **Lesson for future question design: site status-quo / no-action outcomes at a
pole (0 or 100), not the midpoint**, so that a mid-scale forecast is informative rather than the
default a dispersed field produces. The sealed IAEA forecasts and all grading rules stand unchanged;
this is guidance for the next question's continuum, not a change to this one.

### D29.1 — `schelling precedents`: the outside view
New command `schelling precedents <game-or-draft.json> [--search]` runs one LLM call that identifies
prior comparable decisions — same body, same dyad, same institution, same decision type — and for each
emits what happened, its date, a source citation, a PROPOSED placement on the current question's 0-100
continuum, and one line of reasoning (`src/schelling/precedents/find.py`). It writes a precedents draft
(`PrecedentSet`); **nothing is auto-accepted**. Replayable via any `LLMClient` (tested with a replay
client; CI never calls the live API).

### D29.2 — Ratification, same discipline as the case library
Every placement is a **proposal until a human ratifies it** (`Precedent.ratified`, default False). A
set is ratified only when the human sets `ratified: true` on accepted placements AND quotes their
ratification in `PrecedentSet.ratification_note` (`is_ratified`); the ratification is quoted in the
rendered panel. Each precedent is flagged **ex-ante-codable vs hindsight-coded**; only ex-ante
precedents form the base rate, and hindsight-coded ratified ones are **reported separately**. The
attach helpers refuse an unratified set.

### D29.3 — Reference-class panel: separated, disclosed, NEVER blended
`build_precedent_panel` maps the ratified ex-ante placements through the current rubric's bands into a
`PrecedentPanel` (schemas/forecast.py) attached to the record like the ICB analog panel. The report and
dossier render it as its OWN band strip beside the model's — a clearly-separated section headed
"Reference class — the outside view", disclosing that it is a base rate, **not** a forecast, and
**never blended** (`blend_weight = 0`, exactly the ICB rule, D11.2).

### D29.4 — Feed the evidence river; firewall unchanged
`formalize --precedents <ratified.json>` adds each ratified precedent to the formalizer's `sources`, so
it joins `allowed_text` and the model may cite it for position/salience coding ("this actor voted X in
the comparable 2024 decision"). Precedents are EVIDENCE; the concepts library still may not testify —
the firewall is unchanged (a precedent in `allowed_text` is legitimate provenance, a concept phrase is
not). Ratification-gated (`_precedent_evidence`).

### D29.5 — Divergence diagnostic: outside view vs structural model
When the model's median and the precedent base rate (the modal band of the panel) fall in **different**
rubric bands, `divergence`/`divergence_line` produce a named diagnostic —
"OUTSIDE VIEW DISAGREES WITH STRUCTURAL MODEL", stating both bands — printed in **solve** output, the
**report** (a caveat in the panel section), and the **dossier**.

### D29.6 — Tests
`tests/test_precedents.py`: no auto-acceptance (finder proposals all unratified), parse rejection +
skip-malformed, ratification gating (panel refuses unratified; ex-ante/hindsight split), panel
separation (disclosed + `blend_weight = 0` + ratification quoted), divergence firing only across bands,
determinism, the evidence-river ratification gate, and the CLI (`precedents` writes an unratified draft;
`solve --precedents` attaches + prints divergence; `dossier --precedents` never modifies the record).
Sealed records are untouched — a panel is attached post-hoc via `model_copy`, outside `inputs_hash`,
and the dossier attaches read-only.

### D30.0 — Bugfix: `precedents` failed "no JSON array" on --search (token truncation)
Diagnosed from the live response on `analyses/iaea/iaea.json --search` (raw dumped to a scratch file):
**22 blocks** (4 thinking, 2 text, 8 server_tool_use, 5 web_search_tool_result, 3
code_execution_tool_result), **`stop_reason: max_tokens`**. The client's block-parsing already
concatenates only `text` blocks correctly (one implementation, in `formalizer.client._parse_response`
— precedents did not duplicate it), and that concatenation was **preamble only** (511 chars: "I'll
research… Note: live web search was rate-limited…"): the model spent its 4000-token output budget on
thinking + tool use + a wordy preamble and was **truncated before emitting the array**. So there was
genuinely no `[`/`{`/fence and the extractor correctly reported none.

**Fix (D30):** (1) raised `_MAX_TOKENS` 4000 → 8000 and made the system prompt demand JSON-only (no
preamble, no notes, no fences); (2) hardened `parse_precedents` to tolerate ```json fences, a preamble
before/after the JSON, a `{"precedents": [...]}` wrapper, and a **single object** instead of an array;
(3) `find_precedents` now **retries once** with a stricter JSON-only instruction, and on final failure
raises with the **first 300 characters of the last response** so the failure is diagnosable, not
opaque. Replay fixtures cover the exact failing shape (preamble-only → retry → array) and each
tolerated shape. Confirmed live: `precedents analyses/iaea/iaea.json --search` now returns 11 IAEA
Board precedent proposals. 427 tests green.

### D30.1 — Selection-bias lesson: the reference class is SESSIONS-AT-RISK, not notable outcomes
The D30.0 live run returned **11 proposals — every one a censure, referral, or non-compliance
resolution** (placements 2–30, all in action bands). That is a textbook **selection-bias** reference
class: it enumerated the *notable outcomes* and silently dropped every Board session that met and
adopted nothing. A base rate over that numerator with no denominator overstates the probability of
action — precisely the error the outside view is supposed to guard against. The quiet sessions are
not absences; each is a decision opportunity that **places in the no-action band (40–59)** and belongs
in the class.

**Standing rule (now in `docs/PRECEDENTS.md` and the finder's system prompt):** identify the
*population of decision opportunities* FIRST — every occasion the decision could have been taken, from
a stated start date — and only then record what each one decided. Silent non-events are part of the
class. Enumerate the denominator before you count the numerator. The lesson is general, not
IAEA-specific: any base rate is meaningful only over its population of opportunities.

### D30.2 — Denominator correction: INCOMPLETE beats a biased base rate
Schema + panel changes implementing D30.1. `PrecedentSet` and `PrecedentPanel` gained `reference_class`
(the population definition + start date, as the model states it) and `sessions_at_risk` (the
denominator; **null = enumeration not fully sourced**). The finder now returns a JSON *object*
`{"reference_class", "sessions_at_risk", "precedents"}`; the system prompt demands the population first,
places no-action sessions in the no-action band ("do not list only the dramatic outcomes; that is
selection bias"), and sets `sessions_at_risk` to null when the enumeration cannot be sourced.
`_extract_top_json` prefers the whole object (carrying the metadata) before falling back to a bare
array; `_parse_response` returns `(precedents, reference_class, sessions_at_risk)`.

`build_precedent_panel` computes a band distribution — and therefore a base rate and the divergence
diagnostic — **only when the class is COMPLETE**: `sessions_at_risk is not None and n_covered >=
sessions_at_risk` (the ratified ex-ante precedents span the population). Otherwise the panel is
INCOMPLETE: `band_distribution={}`, `base_rate_band → None`, `coverage_fraction = n_covered /
sessions_at_risk` (or None), and the report renders an INCOMPLETE caveat ("N of M sessions-at-risk
covered … no base rate is computed") instead of a distribution. `divergence` was already None whenever
`base_rate_band` is None, so an incomplete class **cannot** fire the outside-view diagnostic.

**Confirmed live (item 3).** Re-running `precedents analyses/iaea/iaea.json --search` with the
corrected prompt returned **9 proposals across the June-2024 → June-2026 Boards — including 4
no-action sessions placed ~50** (the quiet Boards the D30.0 class dropped). The model **reported the
population as INCOMPLETE itself** (`sessions_at_risk: null`), because the outcomes of the Sept-2025 /
Nov-2025 / Mar-2026 Boards could not be independently sourced. Building the panel against the sealed
IAEA compromise record (model median **50.5** → "No new resolution; report noted; left to the
diplomatic track"): reference class **INCOMPLETE**, coverage fraction unknown (denominator null), **no
base rate, and the divergence diagnostic does NOT fire**. The D30.0 false divergence (the outside view
"disagreeing" with the model's no-action median) was an artifact of the biased outcome-only sample; the
sessions-at-risk enumeration plus honest INCOMPLETE reporting removes it. All gates green.

### D31.0 — The site: generated, never written
`schelling site build` regenerates a static site under `docs/`, published via GitHub Pages (main
branch, `/docs`). Plain HTML + one CSS file (`docs/site.css`), plus a `.nojekyll` marker so Pages
serves the files verbatim. No framework, no build step, no external fonts or scripts — the same
offline-clean rule as the reports. The site lives in `src/schelling/site/` (`data.py` gathers,
`css.py` is the stylesheet, `render.py` builds and diffs the pages) and the CLI adds `site build
[--check]`. Five pages: **index** (thesis, the four movements, the finding in three sentences, the
live ledger with a countdown and how-to-verify), **ledger** (full table, per-question rubric links,
`schelling verify` + `ots verify`), **findings** (pre-registered gates & verdicts, the ceiling, the
successor leaderboard), **paper** (abstract, a link to DRAFT.md, the bibliography), **reports** (an
index of rendered dossiers copied into `docs/reports/`).

### D31.1 — Every figure traces to an artifact
`site.data.gather()` parses every number the pages quote from a committed artifact — the sealed
ledger `FORECASTS.md` (rows, hashes, medians, frozen/resolution/grading dates), `BACKTEST.md` (the
gate verdict and the leaderboard marker block), `paper/EVIDENCE.md` (headline figures via the
paper's own `parse_evidence`, and the test count from its `E-TESTS` row), and `DECISIONS.md` (the
decision count). No figure is hand-typed into HTML; the page builders interpolate only fields of
`SiteData`. This mirrors the concepts firewall in spirit: the site *displays* computed numbers, it
never originates one.

### D31.2 — Determinism, and why the site stamps no live HEAD or pytest count
`site build --check` fails if the committed site differs from a fresh regeneration (added to CI after
`paper-evidence --check`). For that to be stable, `gather()` reads only committed files — **no git,
no pytest subprocess, no wall clock**. Two figures the plan listed as "generated" were deliberately
*not* baked into page content:
- **The HEAD sha.** A live HEAD stamp can never satisfy `--check`: the very commit that publishes the
  site changes HEAD, so a post-commit regen would always differ. Provenance is instead the committed
  artifacts themselves (which already carry git provenance in EVIDENCE.md).
- **The test count.** Sourced from `EVIDENCE.md`'s `E-TESTS` row (a committed artifact, the same
  figure the paper cites) rather than a live `pytest --collect-only`, so adding a test does not
  silently desync the published site, and CI regenerates the identical bytes. When the paper's
  evidence is next regenerated, the site follows.
- **The countdown.** A build-time day count would bake a wall-clock value into hashed content
  (breaking rule 2 *and* `--check`). So the page ships the static target date only, and a single
  tiny **inline** script computes days-remaining client-side at view time — self-contained, offline,
  no network. This is the one script on the site.

### D31.3 — Offline-cleanliness, precisely scoped
Each page renders fully offline: the only external references are **navigational** `<a href>` links
to the public repository (rubrics, `DRAFT.md`, `FORECASTS.md`) and — inside copied reports — source
citations. No **embedded** resource is ever loaded off-site: no external `src=`, no external
stylesheet `<link>`, no `@import`, no `url(http…)`, no webfont. Repo-root artifacts (rubrics, the
draft) live above `docs/` and are not served by Pages, so they are linked at the public repo URL
(`--repo-url`, default `hamzagul07/schelling`), which is a navigation target, not a resource load.

### D31.4 — Design: honor the reports' system
Editorial and restrained, reusing the reports' existing palette (accent amber `#b45309`) rather than
inventing one — the correct precedence (the project's own system over fresh choices). Serif
(Georgia) for the thesis lines, system-sans for body, monospace for hashes/ids; one accent; 0.5px
hairlines; no gradients or shadows; dark mode via `prefers-color-scheme`; a print stylesheet; fully
responsive. System font stacks only — no webfont — so the "no external fonts" rule holds with zero
fallback risk.

### D31.5 — Honesty rules baked into the template
The ledger always prints the **graded count beside the sealed count** ("N sealed · M graded"). A
question counts as graded only once its `GRADING-<qid>.md` carries an `Actual outcome:` line — a
pre-registered rubric alone does not — so today `graded == 0` and the banner states plainly that no
page claims forecast accuracy. Any page quoting a forecast shows its resolution date and a
sealed/graded chip. The `findings` page reports the DEU **backtest** (clearly a retrodictive
benchmark, never the sealed live forecasts), so no page claims live accuracy while `graded == 0`.

### D31.6 — Tests
`tests/test_site.py` covers: **generation determinism** (byte-identical rebuilds), **the drift
check** (`check_site` returns `[]` after a write and flags a mutated or missing page), **no
hand-typed figures** (every number in each page traces to `SiteData.provenance()` — a tokenizer that
reads text hyphens in `utf-8`/`SHA-256`/`Q-2026` as text, not negative signs, and treats a digit
inside a hex hash as non-figure; entities and the inline script are scrubbed first), and
**offline-cleanliness** (no embedded external resource on any generated page or copied report). Plus
a real-repo integration test that `gather()` parses the committed artifacts and the published `docs/`
is in sync. 13 site tests; 442 in the suite.

### D32.0 — Vercel deployment: a static site, not a Python app
Vercel's build failed with *"No python entrypoint found in default locations"* — it detected
`pyproject.toml`, assumed a Python serverless project, and looked for an app entrypoint. This repo is
not a serverless app: the deployable artifact is the static `docs/` folder produced by
`schelling site build`. Fixed with two hand-authored root config files (config only — no change to
the generator, the drift check, or the honesty rules):

- **`vercel.json`** — `framework: null`, `installCommand: ""`, `buildCommand: ""`,
  `outputDirectory: "docs"`, `cleanUrls: true`, `trailingSlash: false`. The **empty strings** (not
  `null`) are what actually skip the install and build steps; the previously-committed `vercel.json`
  used `buildCommand: null`, which lets framework detection run — the cause of the failure.
- **`.vercelignore`** — hides everything Vercel must not see so framework detection cannot fire at
  all: `src`, `tests`, `pyproject.toml`, `uv.lock`, `data`, `runs`, `paper`, `analyses`,
  `docs/papers`. Nothing outside `docs/` is needed to serve the site.

### D32.1 — The drift check ignores config by construction
`site build --check` compares only the seven files `build_site()` produces (five pages, `site.css`,
`.nojekyll`), each under `docs/`; it never enumerates the docs directory or the repo root, so a
hand-authored root file cannot register as drift. `vercel.json` and `.vercelignore` live at the repo
root, outside `docs/` entirely — verified: `site build --check` still reports *no drift*. No exclusion
logic was needed (and none was added — the config files are authored, never generated). README gains
a **Deployment** section: regenerate `docs/` with `site build`, commit, push, the host republishes;
CI's drift check guarantees the published site matches the artifacts.

### D33.0 — Adopt the reference design (styling and markup only)
Hassan dropped `site-reference-index.html` at the repo root as the approved visual target. Its CSS
became `docs/site.css` (adapted, not copied) and the page templates now emit the same structure and
classes. The change is styling and markup **only**: `site/data.py` (the data layer), `check_site`/
`build_site` (the drift check), and the honesty guarantees are unchanged. New palette (warm off-white
`--bg:#fbfaf8`, accent `#b45309`), serif (`ui-serif,Georgia`) used **only** for the `h1` and section
headings, and the reference's nav / stat cards / div-based ledger / gate rows carried across all five
pages. The countdown script is gone (replaced by a "First grading" stat card), so the site is now
entirely script-free.

### D33.1 — Every figure still comes from SiteData; unsourceable elements are dropped
The reference hand-types every number for illustration; the generator does not. Sealed and graded
counts, the next grading date, the test count, every ledger row (question, model, verbatim median,
resolution date, full SHA-256), and every gate label with its numbers are read from `SiteData` —
which is parsed from the sealed ledger, the evidence table, and the leaderboard. The
no-hand-typed-figures test still passes: every number in the HTML traces to `SiteData.provenance()`.
Where the generator's figures differ from the reference's illustrations, the sourced value wins
(e.g. the test count renders `297` from `EVIDENCE.md`'s `E-TESTS`, not the reference's `442`; dates
render ISO from the rubric files, not `1 Sep`; question labels render the canonical id, not a
hand-written prose name). `_gate_rows` **drops** any gate whose numbers cannot be sourced rather than
inventing a source (D33.2), and shows all five only because every figure resolves from the evidence
table and the leaderboard.

### D33.3 — The honesty rules, in the new markup
The ledger still shows the **graded count beside the sealed count** — now as adjacent `Forecasts
sealed` / `Graded` stat cards, present on both the index and the ledger page. While `graded == 0`
the ledger note states plainly that nothing is graded, so no accuracy is claimed; no page asserts
forecast accuracy. The honesty test was updated to assert the new stat-card markup (the guarantee is
unchanged — only the string it checks moved from `N sealed · M graded` to the two adjacent cards).

### D33.4 — Specifics locked against drift
A `test_reference_design_structure_holds` guard asserts the details that must not drift: a two-line
serif `h1` whose second line (`.turn`) carries the accent and whose first does not; **no HTML tables
anywhere** (hashes never live in a table cell); the full 64-char SHA-256 on its own 11px monospace
`.hash` line beneath each row; the nav with a monospace brand plus navlinks. The ledger shows **all**
sealed rows (eight), not the reference's five. CSS holds the rest: body copy capped at 62–66ch, two
font weights only (400/500), 1px hairlines, no shadows or gradients, dark mode via
`prefers-color-scheme`, and a mobile breakpoint that reflows rows and hides the header row —
`site.css` keeps its per-file E501 ruff ignore as a stylesheet asset. 443 tests green;
`site build --check` in sync; `docs/` regenerated.

### D34.0 — The instrument layer: two figures generated from artifacts
Two deterministic inline-SVG figures, same rule as the report figures — no hand-plotted coordinate,
every mark positioned from a sourced value (`src/schelling/site/figures.py`). **Fig. 1, the forecast
landscape** (index + ledger): one group per sealed question, one row per model forecast, the median
as a dot and the 80% interval as a bar on the question's 0-100 continuum, with the rubric band
boundaries drawn behind as thin rules and the modal band — the band holding the most model medians —
tinted and labelled; the resolution date sits at the right of each group, a legend above, and it
scales to any number of questions. **Fig. 2, the trials** (findings): a horizontal bar pair per
pre-registered MAE gate (model vs baseline on one shared scale) with the verdict as a monospace
label, ordered as the tests ran so it reads as a sequence of attempts. Both are `role="img"` with a
generated `<title>`/`<desc>`, byte-identical on re-run, and free of scripts/external assets. Data
marks reuse the report renderer's palette (amber for the 0-end half, teal for the 100-end); the
palette's dark structural colours would vanish on a dark ground, so axes, band rules, and every
label instead use the site's CSS variables (`fig-*` classes) and flip with `prefers-color-scheme`.

### D34.1 — The committed interval snapshot (FORECAST-INTERVALS.json)
Fig. 1 needs each forecast's 80% interval, which lives only in the gitignored `runs/` records —
absent on CI, where `site build --check` must pass. Reading records at build time would make the
committed site un-reproducible on CI. So the intervals are snapshotted into a committed file,
`FORECAST-INTERVALS.json`, keyed by the ledger SHA-256; `gather()` reads only that committed snapshot
(a pure function of committed files), and `site build --refresh-intervals` regenerates it from the
records locally (matching each ledger row to its record by SHA-256, exactly as `schelling verify`
does). The medians remain governed by `FORECASTS.md`; the snapshot adds only the interval endpoints
of the already-sealed records, so disclosing them early **strengthens** the commit-reveal (they
become a visible, un-editable commitment too). `test_intervals_snapshot_matches_records` catches a
stale snapshot wherever the records are present; it skips on CI.

### D34.2 — Fig. 2 is sourced from the backtest, and drops what it can't source
Each trial row's model and baseline MAE come from the evidence table (`E-DEU-MAE-r1`,
`E-BASE-WMEAN-r1`, `E-METHOD-challenge_rp`, `E-METHOD-baseline_wmean`, `E-ORACLE-MAE`) and the
successor leaderboard (TEST vs comp columns, located by header name) — all committed, all tracing to
`BACKTEST.md`. A gate whose numbers cannot be parsed is dropped, never invented, exactly as the gate
text rows do (D33.2). `test_trials_plot_the_sourced_maes` asserts the plotted MAEs equal the values
parsed independently from the artifacts.

### D34.3 — The no-hand-typed-figures rule, extended to SVG
The figures put hundreds of computed coordinates into the HTML. Those are geometry, not hand-typed
figures, so the no-hand-typed-figures test scrubs `<svg>…</svg>` (as it already scrubs `<script>`)
before scraping numbers from the prose and tables — which must still all trace to
`SiteData.provenance()`. The figures' *data* is guarded separately and more strictly:
`test_landscape_plots_the_sourced_values` recomputes each median's x-coordinate through the figure's
own continuum scale and asserts the dot and interval bar are plotted there, and
`test_trials_plot_the_sourced_maes` checks Fig. 2's bar labels. `"80"` (the fixed interval level)
joins `"256"` (SHA-256) in the structural whitelist.

### D34.4 — Typographic instrumentation, restrained
A hairline rule above each section (its `border-top`) with the section number in monospace at the
left — the ordinal is a **CSS counter** (`.snum::before { content: "§ " counter(sec,
decimal-leading-zero) }`), so no number is hand-typed into the HTML. Monospace for every identifier
and figure caption (question ids wrapped in `<code>`, `Fig. 1` / `Fig. 2`, run-id/hash strings),
hashes already on their own 11px monospace line, and `font-variant-numeric: tabular-nums` on the body
so every column of digits lines up. No stamps, no fake classification markings — the credibility
comes from precision, not costume. 448 tests green; `site build --check` in sync; `docs/`
regenerated; the honesty rule, drift check, no-hand-typed test, and offline-cleanliness all still
pass.

### D35.0 — The full-scale layout: adopt the vast reference (structure and CSS only)
Hassan dropped `site-reference-vast.html` at the repo root as the approved target. `site.css` and the
page shell now follow it — the data layer, the drift check, the honesty rule, and the
no-hand-typed-figures test are unchanged (item 5 does add two new *sources*, below). A sticky 260px
left sidebar carries the numbered section index and a sealed/graded line in its footer; the content
column is full-bleed with `clamp(28px,5vw,96px)` side padding and collapses to a horizontal bar under
900px. The type scale is the reference's: hero `clamp(40px,7.2vw,104px)`, section headings
`clamp(22px,2.2vw,30px)`, the `.big` pull-quote `clamp(20px,2vw,27px)`, tabular figures throughout,
new palette (warm `#faf9f6` ground, accent `#a8480d`, teal `#0f6e56`), dark mode via
`prefers-color-scheme`. Section ordinals are CSS counters (`.sechead .n::before`, `.idx .n::before`),
so no ordinal is hand-typed. The **index is restructured into the reference's eight sections** —
finding, ledger, trials, apparatus, canon, record, paper, verify — and the existing pages
(`ledger.html`, `findings.html`, `paper.html`, `reports/`) are kept and deep-linked from each section
(and re-housed in the same sidebar shell).

### D35.1 — Figures rescaled full-bleed to a 1200-unit viewBox
Both instrument SVGs regenerate at a 1200-unit viewBox and render full-bleed at the content width
(not inside a text column). The forecast landscape is now coloured by **model family** — challenge
amber, compromise teal, llm-judgment grey, all three drawn from the report renderer's palette (the
palette's dark structural colours would vanish on a dark ground, so only the data marks use it;
axes, rules and labels use the site's CSS variables and flip with dark mode). The trials figure keeps
the model-vs-baseline bar pairs on a shared scale with the verdict as a monospace label. Both stay
pure functions of the artifacts, byte-identical on re-run, `role="img"` with a generated title/desc,
and script/asset-free. The landscape headlines the index ledger section and the trials headline both
the index trials section and the findings page.

### D35.2 — The two new data sources; sourced values win over the reference's illustrations
Every figure in the reference is hand-typed for illustration; the generator sources them. Two
sections that previously had no data source now do (item 5): the **canon** section reads its card
count (29) and family names from `data/concepts/canon.md` (one card per `**X#.` marker, one family per
`## Family X — name` header), and the **record** section reads the decisions count from `DECISIONS.md`
and the pre-registered-gate count from the backtest/evidence (via `trial_gates`, the same set the
trials figure plots). Both feed a new **grid** of stat cells alongside the sealed/graded/first-grading
figures. Where the generator's sourced value differs from the reference's illustration, the sourced
value wins: **gates render 5** (the enumerable MAE gates), not the reference's 6; **tests render 297**
(the committed `E-TESTS`), not 448; dates render ISO; question labels render the canonical id. A stat
whose count can't be sourced is dropped, not hand-typed (`gate_count`/`test_count` are guarded).

### D35.3 — Honesty and the no-hand-typed rule, in the new markup
The graded count still sits beside the sealed count — now as adjacent `GRADED` / `FORECASTS SEALED`
grid cells on the index and ledger pages, and the sidebar footer states both (`0 graded · 8 sealed`).
While `graded == 0` the ledger prose claims no accuracy; no page asserts forecast accuracy. The
no-hand-typed-figures test is unchanged in intent — every number in the HTML traces to
`SiteData.provenance()` (extended with the question, gate, and canon counts) — with `"3.0"` (the
AGPL-3.0 licence) joining the small structural whitelist. `test_reference_design_structure_holds` now
locks the sidebar shell, the eight-section index, the accented two-line h1, no tables, and the full
64-char SHA-256 on its own `.h` line. 448 tests green; `site build --check` in sync; dark mode and
offline-cleanliness verified on every section; `render.py` gains a per-file E501 ignore as a dense
HTML-template generator (as `css.py` already has).

### D36.0 — E-TESTS is a committed snapshot; refresh it when the suite grows
`paper/EVIDENCE.md`'s `E-TESTS` row is a **committed snapshot** of `pytest --collect-only`, not a
live count. The site publishes it: `site.data.gather()` sources the "TESTS" stat from `E-TESTS`
(chosen in D31.2 so `site build --check` stays stable across the publishing commit and across test
additions — a live count would desync the committed site on every new test). The trade-off is that
the figure goes stale silently: it had drifted to **297** while the suite had grown to **449** (the
site's flagship page showed the old number). Refreshed by regenerating `paper/EVIDENCE.md` with
`schelling paper-evidence` and rebuilding `docs/`. The regeneration changed **only** the `E-TESTS`
value (297 → 449) and provenance git-hashes — **no science number moved, and no figure changed** —
which is exactly the provenance/test-count drift that `paper-evidence --check` classes as a warning,
not a failure (D18.3); after regeneration both `paper-evidence --check` and `site build --check`
report in sync. **No manuscript claim depends on the value:** no draft section cites `[E-TESTS]`, so
`paper/DRAFT.md` is byte-unchanged and needs no reassembly.

**Standing rule:** `E-TESTS` must be refreshed (regenerate `EVIDENCE.md`, then rebuild `docs/`)
whenever the suite grows materially, because the published site quotes it. Neither drift check
enforces this — `paper-evidence --check` only warns on a test-count change, and `site build --check`
only sees the committed snapshot — so the refresh is a manual step, best done in any session that
adds a batch of tests. Logging D36.0 itself grew the decisions count the site's grid publishes, so
`docs/` is rebuilt once more after this entry.

### D37.0 — Q-2026-OPEC-SEP: a fast-resolving, arithmetic-rubric ledger question (setup only)
Third sealed-ledger question, pre-registered from the approved package `question-opec-sep.md`:
what collective crude-production adjustment the seven OPEC+ voluntary-adjustment producers (Saudi
Arabia, Russia, Iraq, Kuwait, Kazakhstan, Algeria, Oman — the group after the UAE's May-2026 exit)
announce for September 2026 at their 2 Aug 2026 meeting. Chosen because it **resolves in nine days**
(resolution 2026-08-05, grading 2026-08-06), sits in the **validated cooperative/DEU domain** where
the compromise model is proven to the ceiling (unlike the coercive US-Iran question), and carries an
**external analyst benchmark**.

- **Arithmetic rubric (not bands).** `GRADING-Q-2026-OPEC-SEP.md` is committed at the repo root
  (public pre-registration; `seal` refuses a rubric-less question). The mapping is a continuous rule
  — `grade = 50 + (adjustment_kbd / 600) × 50`, clamped and rounded — encoded in the machine-readable
  `ResolutionRubric` block **with no `bands` array**, so `parse_rubric_block` reads it as
  arithmetic/linear (the report renders the continuous density strip, not band segments — D22.2) and
  `seal` accepts it. The drift-guard `test_committed_grading_bands_match_outcome_mapping_prose` is a
  hardcoded two-question parametrization, so a bands-less rubric does not trip it.
- **`situation.txt`** was created from the package's paste-ready block verbatim (de-indented) under
  the gitignored `analyses/opec/`; the question rationale doc was moved from the repo root to
  `docs/questions/question-opec-sep.md` (committed) so it sits beside its rubric, matching the IAEA
  precedent.
- **Draft formalized live** (`formalize --search --max-searches 6`, $0.80, 6 searches, 38 sources,
  stamped `frozen_at=2026-07-24`, `live_searched=true`): 7 actors, template *Multilateral / Coalition
  Bargaining*. The one hard-sourced datum is the group's **5 July +188 kb/d collective increase**
  (used the primary/wire reading, not the lone aggregator that called it a cut); every actor-level
  position, salience and capability is **inferred and disclosed in the assumptions** (capability rule
  = production weight / move-or-block ability, Saudi=100 down to Oman≈8; the 2 Aug date and the
  post-withdrawal roster are assumed, not source-confirmed).
- **STOPPED at the draft** (D12.5 human-review gate): not solved, not sealed. Hassan reviews the
  draft with Claude before any forecast is run. `analyses/opec/` (situation, draft, report) stays
  gitignored; only the rubric, the rationale doc, and this entry are committed.

### D37.1 — Sealed Q-2026-OPEC-SEP v1-thin (the honest thin-sourcing baseline)
Hassan directed sealing the v1 draft as-is — its value is as the low-sourcing baseline against which
a better-sourced v2 is measured. Sealed all three records at `--vintage v1-thin`: **challenge 62.009,
compromise 62.450, llm-judgment 58.000** (`frozen_at 2026-07-24`). The two solver records verify 4/4
(`schelling verify`: ledger-match, inputs-hash, determinism); the llm record is a SHA-256-only
commitment (non-deterministic, D27.2) so `schelling verify` doesn't apply to it — its integrity is the
ledger sha + OTS anchor, exactly like the USIRAN/IAEA llm seals.

- **One correction before sealing (approved out-of-band).** The formalizer had set the draft's
  `question_id` to `Q-2026-OPEC-SEP-VOLADJ`, which mismatched the pre-registered
  `GRADING-Q-2026-OPEC-SEP.md` and would have produced an ungradable seal (the rubric lookup keys on
  `question_id`). Corrected `question_id` → `Q-2026-OPEC-SEP` (metadata only — no actor, coordinate,
  evidence or forecast value changed; the thin baseline is preserved) and re-solved.
- **Rubric attachment.** `solve` does not embed the rubric, so the two solver records were sealed with
  the arithmetic `ResolutionRubric` injected from the GRADING file (hash-excluded, so `verify` still
  reproduces); the llm record picked it up via `llm-forecast`'s read-only lookup.
- **Ledger + site.** The seal added three rows and re-anchored `FORECASTS.md` (OTS). OPEC now resolves
  **2026-08-05** — earlier than USIRAN (08-31) and IAEA (09-30) — so the ledger header's date line
  (which the site publishes as "first grading") was updated to the earliest, 2026-08-06, and
  re-stamped; `FORECAST-INTERVALS.json` refreshed to 11, `docs/` rebuilt (11 sealed). All checks green.

### D37.2 — Targeted v2 re-formalization: sourcing improved, unevenly, and honestly
Re-formalized to `analyses/opec/opec-v2.json` (`--search --max-searches 12`, **$1.23, 12 searches, 82
sources** vs v1's 6/38) with explicit search directives added to the situation NOTES (delegate-sourced
positions; per-producer IMF fiscal breakevens; compensation schedules since Jan 2024; chronic
overproduction and unwinding stances; confirm the 2 Aug date from OPEC; cite the OPEC Secretariat
statement directly; and — per the brief — a capability rule accounting for **above-quota production
ability as power**). `question_id` came back correct this time.

**Acceptance test — sourced vs inferred, v2 vs v1, stated plainly (no dressing up):**
- **Genuinely new sourced evidence in v2:** the OPEC Secretariat statement cited directly
  (opec.org 3 May 2026, membership); the **2 Aug meeting date** now sourced (Saudi Gazette) and not
  reported to have moved; **per-country compensation schedules** (Interfax: Kazakhstan ~2.63 mbpd,
  Iraq ~1.4 mbpd, Russia ~0.31 mbpd); **Kazakhstan's chronic, unenforceable overproduction** as
  bargaining power (OilPrice); **Saudi Arabia's fiscal breakeven** (~$86.60, IMF-style). The +188 kb/d
  **increase** reading is retained (wires, not the aggregator).
- **Capability rule (brief item 3) satisfied and disclosed:** Saudi = 100; others scaled by a blend of
  production weight, spare capacity, AND demonstrated above-quota production — Kazakhstan lifted above
  its bare volume share (cap 12/20/30 → 22/32/45) because its unenforceable overproduction is itself
  moving/blocking power.
- **But the coordinates themselves are still inference, and unevenly:** by the draft's own assumptions,
  **no actor's position is delegate-sourced** (assumption 5 — pre-meeting positions weren't
  retrievable), and salience is directly sourced **only for Saudi Arabia** (assumption 6). The four
  big/pivotal members (Saudi, Kazakhstan, Iraq, Russia) now rest on real actor-specific evidence
  (compensation, overproduction, breakeven); the three small members (**Kuwait, Algeria, Oman**) are
  **unchanged from v1** — only "named in the OPEC statement" plus a generic "consensus follower," all
  three coordinates pure inference. So the honest verdict: the **evidence base under the inferences
  improved materially for the members that matter**, but the position/salience/capability values
  remain grounded estimates, not sourced points — a real improvement, not the same inference re-cited.
- **STOPPED before solving v2** (item 5). v2 is a draft under the human-review gate; `analyses/opec/`
  (v1/v2 drafts, situations, reports) stays gitignored. Only the v1-thin seal (FORECASTS.md,
  ledger-proofs, intervals, docs) and this log are committed.

### D37.3 — Sealed Q-2026-OPEC-SEP v2-sourced, after a targeted pause check
One targeted search (2026-07-24, via WebSearch — not a re-formalize) for any member favouring
**pausing or reversing** the September unwind: none found. July-2026 reporting consistently expects
the seven to add ~188 kb/d for September, treating the monthly schedule as fixed policy even with
Brent above $100. The group's **Q1-2026 pause is real precedent** (Jan–Mar, Russia/Novak-led) but its
triggers — seasonal demand slowdown + an oversupply glut (IEA ~4 mbpd surplus) — are **not** cited for
September; the current driver is the Strait-of-Hormuz supply disruption and high prices, which favour
adding barrels (analyst oversupply worry is only a forward risk "once transit normalises"). Sources:
Al Jazeera 2026-07-06; investinglive/Bloomberg; Reuters via Investing.com; Forbes/Astana Times.

- **Widening (item 2, second branch).** With no member favouring a pause, the low end of **every**
  actor's position range was widened to **45** (a small ~90 kb/d cut) so a pause/reverse outcome sits
  inside the ensemble support rather than outside it, recorded as an explicit assumption. No mode was
  moved below 50 — a pause is *possible* (precedent + retained flexibility) but not currently favoured
  by anyone, so it belongs in the tail, not the centre. The widening moved the CI80 lower bound down,
  not the pinned weighted median.
- **Sealed v2-sourced (three records):** challenge 63.680, compromise 63.434, llm-judgment 66.000
  (frozen 2026-07-24). Solver records verify 4/4; the arithmetic rubric was attached to the v2 draft
  before solving, so no post-hoc injection was needed this time. `FORECAST-INTERVALS.json` refreshed
  to 14, `docs/` rebuilt (14 sealed), OTS re-anchored on each seal.
- **The sourcing experiment, side by side** (Q-2026-OPEC-SEP, all three families):

  | Model family | v1-thin | v2-sourced | Δ |
  |---|---:|---:|---:|
  | challenge    | 62.009 | 63.680 | +1.67 |
  | compromise   | 62.450 | 63.434 | +0.98 |
  | llm-judgment | 58.000 | 66.000 | +8.00 |

  Better sourcing barely moved the two solver medians (both pinned near the group's revealed +188
  pace) but lifted the llm judgment from 58 to 66 (its 80% interval shifting from [48,66] to [50,75])
  — the model, given the compensation/overproduction/fiscal evidence, grew more confident the group
  continues the August pace. Both vintages are now gradable against the same arithmetic rubric on
  2026-08-06; the experiment (does targeted sourcing change the forecast?) is visible in the ledger.
- **Operational note.** The v2 `llm-forecast` first failed on an exhausted Anthropic API credit
  balance; Hassan topped up and it completed. Both OPEC formalize passes + three llm-forecast runs are
  what drew the balance down.

### D38.0 — Deep research mode: iterative evidence gathering to a reproducible corpus
New `schelling research <situation.txt> [--budget N] [--resume]` and `schelling formalize --corpus
<dir>` (`src/schelling/research/`). Research gathers evidence in **rounds** — a broad survey, then
targeted searches for the coordinates the game needs but lacks, then a contradiction-resolution pass
— and **stops when a round adds no new claim** (`marginal`), when no gaps remain (`no_gaps`), or when
the running spend reaches `--budget` (`budget`), rather than after a fixed number of searches. It is
**resumable** (reload the corpus and continue) and **caches sources by URL** (`merge_round` drops a
URL already present, keeping its original retrieval date). The LLM only *structures* evidence
(extracts claims, tags confidence, names gaps) — it produces no probability (rule 1) and never
consults the concept index (the firewall is unchanged; CI stays offline via `ReplayClient`).

### D38.1 — The corpus and its confidence tags
The corpus (`corpus.json` + `situation.txt`) records every source (title, url, retrieval date) and
every claim with a **confidence tag**: `established` (multiple independent primary sources),
`reported` (a single credible source), `contested` (sources disagree — every reading recorded), or
`inferred` (no source; the model's reasoning, stated as such). A coordinate's confidence is
**derived** from its claims (`ResearchCorpus.coordinate_confidence`), not asserted: a coordinate whose
claims record more than one distinct reading, or any claim tagged contested, is `contested` and can
never be silently resolved to one side.

### D38.2 — Offline, reproducible formalization; confidence drives width by a committed rule
`formalize --corpus <dir>` feeds the corpus to the existing formalizer with **search OFF** — the
draft is reproducible from a fixed evidence set (the situation hash must match). The committed rule
`research/confidence.yaml` (a config file, not prose, so it can be cited and audited) maps confidence
to a half-width on the 0-100 continuum — **established narrows (4), reported widens moderately (12),
inferred widest (22)** — and `apply_confidence_widths` rewrites each coordinate's range from that rule
after formalizing, keeping the formalizer's mode. A **contested** coordinate's range spans its
disagreeing readings (never one side): the contradiction widens the range. Every claim still lands in
an evidence note or the assumptions list (the firewall path is untouched), and `--budget` caps spend
with a per-round spend report. Tests (`tests/test_research.py`, 12): gap identification feeds the
targeted round, cache dedup preserves the first retrieval date, resume continues a prior corpus,
contradictions widen across readings, the confidence-to-width rule loads from the committed config,
and corpus-offline formalization is deterministic. 460 tests green.

### D39.0 — An integer engine version, distinct from provenance SHA and from the hash epoch
A record now pins *which solver numerical path produced it* with an explicit integer,
`ForecastRecord.engine_version` (v1 = the Session 1–38 behaviour). This is deliberately three
separate identifiers that had been conflated: `engine_version` (int) is the **numerical path**;
`engine_sha` (str) is the engine's **git commit** for provenance; and `inputs_hash`'s v1/v2
**canonicalization epoch** (D18.1) is how a record is content-addressed. The pre-D39 record stored
the git SHA in a string field also named `engine_version`; a `model_validator(mode="before")`
migrates any such legacy record — moving the SHA to `engine_sha` and defaulting the integer to 1 — so
every record on disk still loads and no sealed byte changes. The rename is scoped to `ForecastRecord`
only: `LLMForecastRecord`, `BacktestRecord`, and `AdviseRecord` keep their own string `engine_version`
(they are SHA-committed, not re-solved), and the git-SHA helper `monte_carlo.engine_version()` was
renamed `engine_sha()` to match. Interpretive note: the task said "add an integer and a registry"; the
one real choice was rename-vs-additive for the clashing field name — rename was chosen as the literal
reading, bounded by testing that both a legacy dict and a real sealed OPEC record still load (v1 +
recovered SHA) before touching anything downstream.

### D39.1 — A solver registry; verify re-solves under the record's declared version
`solver/registry.py` maps each engine version to its own solve entrypoint
(`ENGINE_REGISTRY = {1: _solve_v1}`, `CURRENT_ENGINE_VERSION = 1`). `schelling verify` now re-solves
through `resolve(record.engine_version)` — the version the record was **sealed under** — not the
current default. New records stamp `CURRENT_ENGINE_VERSION`. The **freeze rule** (documented in the
module): never edit a released version's numerical path; to change numerics, register a new integer
version and bump `CURRENT_ENGINE_VERSION`. This is the seam the whole engine expansion hangs off — v1
is now addressable and immutable.

### D39.2 — The permanent regression gate: every sealed record verifies 3/3 under its own engine
`test_all_sealed_records_verify_under_their_engine` iterates every sealed solver record in `runs/`,
re-solves it through the engine version it was sealed under, and asserts 3/3 (`report.ok`). This is
the standing gate for the entire expansion: any future change that would move a v1 median fails here.
It is data-gated the same way as the other record tests — `runs/` is gitignored (commit-reveal), so
the gate runs wherever the records are present (locally) and skips on CI. Locally it checks all sealed
records green.

### D39.3 — PASS-with-note, not FAIL, when a version is genuinely retired
Where a build no longer ships the engine version a record was sealed under, `verify` reports the
determinism check as **PASS-with-note** — *hash and ledger match, but the ensemble is not re-derivable
under the current engine* — rather than FAIL. The SHA-256 + ledger commitment is intact and
authenticated; only re-derivation is unavailable, and conflating that with tampering would be
dishonest. The policy is recorded in `FORECASTS.md` (a new *Engine versioning* section), which will
also list any record that enters that state. As of this session none has: all records declare v1,
which this build ships, so all verify 3/3. Tests (`tests/test_engine_version.py`, 6): the registry
shape, new records declaring the current version, the legacy-string migration, verify re-solving under
the declared version, a retired version reported PASS-with-note (not FAIL), and the permanent
regression gate. 466 tests green.

### D40.0 — Phase B is analysis-only: no solver, MC, or sealed number touched
Phase B adds three post-hoc analysis layers — proper scoring, power indices, Sobol sensitivity —
and nothing in the session alters a solver, the Monte-Carlo engine, or a sealed number. The D39.2
regression gate is the enforcement: it re-solves every sealed record under engine v1 and passes
untouched this session, so the guarantee is checked, not merely asserted. Everything new is a pure,
deterministic, LLM-free reader of an existing record, a weighted-voting input, or a game's ranges.

### D40.1 — Proper scoring rules, computed alongside the sealed primary (never replacing it)
`backtest/scoring.py` scores a record against a realized outcome with a **proper** rule — one that
reads the whole draw distribution, not just the median. Banded rubrics get the multi-category
**Brier** score `sum_i (p_i - y_i)^2` and the **logarithmic** score `ln(p_realized)`, with the
probability vector taken from the share of cached draws in each band (the same `report.bands.map_bands`
mapping). Arithmetic rubrics get **CRPS** of the empirical draws, evaluated by the O(n log n)
sorted-sample identity; **CRPS reduces to `|forecast - actual|` at a point mass**, so it generalizes
the ledger's absolute-error metric rather than replacing it (hand-verified in `tests/test_scoring.py`:
Brier 0.38, log ln(0.5), CRPS 2.5, and point-mass collapse). Orientation (lower/higher better) is
carried on every score so the sign is never ambiguous; a zero-probability realized band is floored at
half a draw (0.5/N) so the log score is finite and disclosed. **Integrity constraint (non-negotiable):**
the three questions sealed before D40 keep `|median - actual|` as primary exactly as their committed
rubrics state. This is enforced structurally: `ResolutionRubric` gains two OPTIONAL fields
`primary_metric` / `secondary_metrics`, both EXCLUDED from `inputs_hash` like the rest of the rubric
(D17.1), so declaring them cannot move a sealed number; an empty `primary_metric` means the legacy
default `absolute_error`, and the three sealed rubrics declare nothing, so `scoring.primary` returns
`absolute_error` for them. A test (`test_sealed_rubrics_keep_absolute_error_primary`) asserts none of
the committed rubrics changed. `docs/GRADING-TEMPLATE.md` now declares the proper rule primary and
absolute error secondary for questions sealed from now on. `schelling compare` reports the proper
scores beside the MAE ranking (secondary, from cached draws when present); its refuse-to-rank guard
(MIN_GRADED=10) is unchanged. Interpretive choice: the logarithmic score is reported in its canonical
`ln(p)` (higher-better) form with an explicit orientation label, rather than as a loss.

### D40.2 — Power indices as an evidence aid, never an automatic assignment
`power/indices.py` computes **Shapley-Shubik** and **Banzhaf** indices for a weighted voting game.
Both use the same swing test and differ only in weighting; small games are solved by **exact
enumeration** of all `2^n` coalitions, and above `exact_max_n` (default 20, exact cost being
exponential) the Shapley index is estimated by **seeded Monte-Carlo permutation sampling** and Banzhaf
by random-coalition sampling, each reported with a binomial **standard error**. Optional **bloc**
structure collapses a group of players that vote together into one player with their summed weight.
Correctness is externally checkable, not self-certified: tests match the published worked examples for
the **1958 EEC Council** (Shapley 0.2333/0.15/0, Luxembourg a dummy; Banzhaf 10/42, 6/42, 0) and the
**UN Security Council** (permanent 0.19627, elected 0.001865). `schelling power` prints the indices
with the rule and quota used and a standing line that it is an AID to be cited by a human — it NEVER
writes a capability value. The formalizer may cite the printed output as a *source* for a capability
in a voting body, exactly as it would cite any fetched evidence; the firewall is unchanged.

### D40.3 — Sobol global sensitivity, a second panel beside the tornado
`mc/sobol.py` adds variance-based **first-order** (`S_i`, the parameter alone) and **total-order**
(`S_Ti`, including interactions) Sobol indices via **Saltelli sampling** (Saltelli-2010 first-order /
Jansen total-order estimators), over the **same triangular input ranges the MC samples** (each ranged
actor field mapped through its triangular inverse-CDF). Both cross designs `A_B` and `B_A` are used to
symmetrize the estimators, at the reported cost of **`N * (2k + 2)` solves** with configurable `N`.
The estimator is validated against the analytic **Ishigami** function (first-order and total-order
within 0.03 of the closed-form values, including x3's zero first-order but non-zero total-order — pure
interaction). The **compromise** solver (closed-form) is the default and runs the full sample quickly;
the **challenge** (BDM) solver is far slower and is gated behind `--solver challenge`, which prints the
solve count first. `schelling sobol` prints the tornado and the Sobol panel together, each explicitly
labelled — tornado = single-parameter swings, Sobol = share of output variance including interactions —
and `--html` writes the two-panel page (`report/sobol_panel.py`). The default forecast report is
untouched, so sealed reports stay byte-identical and `site build --check` is unaffected. Everything is
seeded: same game + N + seed = identical indices. Tests: `tests/test_sobol.py` (5), `tests/test_power.py`
(9), `tests/test_scoring.py` (13). D39.2 regression gate passes untouched.

### D41.0 — Phase C adds solvers as new registry options; no existing path changes
Phase C adds four new `--solver` options plus an opt-in correlated sampler, all registered under the
D39 engine as additive dispatch: `run_monte_carlo` routes the new `model` strings through new
branches and leaves the `challenge` (default `else`) and `compromise` branches byte-identical. The
enforcement is the D39.2 regression gate (every sealed record re-solves 3/3 under engine v1) plus
`test_challenge_and_compromise_are_unchanged` — both pass untouched this session. The one pre-D41
schema touch is a record-level `ForecastRecord.sampling` field (default `"independent"`), which is
NOT in `inputs_hash` (game+config only), so no sealed content-address moves. Per the standing
discipline the gate was **pre-registered and committed (docs/PHASE-C-GATE.md) before any solver code
or DEU run**: a new solver is validated only if it beats the compromise mean on the committed DEU
TEST split with the 95% bootstrap CI (seed 20260721) entirely below zero; otherwise it ships
exploratory, exactly as gravity/regime did.

### D41.1 — challenge-qre: quantal response over the challenge model
`solver/qre.py` softens the challenge model's hard offer acceptance into a McKelvey-Palfrey logit
choice: a mover weights competing offers by `softmax(lambda*enforceability)` (soft choice) and moves
a fraction `phi = sigmoid(lambda*e_max)` of the way to that expected target (soft acceptance). As
`lambda -> inf` both collapse to the exact challenge model; a finite `lambda` makes both soft.
**`lambda = 1.0` is fixed a priori and disclosed** (docs/PHASE-C-GATE.md), never fitted. It is a
deterministic mean-field realization (expected move, no per-draw RNG), so it stays auditable.
Interpretive choice: the naive "soft-select among offers only" is identical to the hard model when a
mover has a single offer (the common case), so the acceptance-fraction softening was added to make
the quantal response bite universally and reduce to the challenge model in the limit. **The median-
lock diagnostic (the point of the exercise):** on DEU the games are point estimates, so there is no
MC spread to compare; on the ranged widened fixture the challenge model is *not* degenerate-locked
(0 of 2 tornado rows zero-swing), and QRE yields a comparable but slightly *tighter* ensemble (CI80
width 1.89 vs 5.17) with marginally more distinct medians — the soft partial moves damp the
full-concession jumps rather than melting a lock. Honest answer for the games available this session:
no strong lock was present to melt; QRE changes the dynamics but does not widen dispersion.

### D41.2 — nash and nash-ks: cooperative bargaining settlements
`solver/nash.py` adds the weighted Nash bargaining solution (`nash`) and Kalai-Smorodinsky (`nash-ks`)
over linear actor utilities `u_i(x) = -|x - p_i|` with the configured reference point as the
disagreement point (else the status-quo weighted median). Nash maximizes `sum_i w_i ln g_i(x)` over
the region where every gain `g_i = |d-p_i| - |x-p_i|` is positive; KS maximizes the minimum
normalized gain `g_i/G_i`. Both by a deterministic 1-D grid line-search, both falling back to the
disagreement point when no outcome Pareto-improves on it (e.g. two opposed actors around a central
disagreement). Hand-verified: opposed pair -> disagreement; `[40,60]` with `d=0` -> Nash 40, KS 48.

### D41.3 — pce: probabilistic Condorcet, the KTAB method
`solver/pce.py` implements KTAB's probabilistic Condorcet election so the library's published
forecasts become directly comparable. Candidates are the distinct actor positions; the pairwise
victory probability is the coalition-support ratio `pv[a,b] = U_a/(U_a+U_b)` (BDM/KTAB victory
exponent 1, equidistant actors split); selection probabilities are the stationary distribution of
`PV` by power iteration (KTAB's `scalarPCE`); the forecast is the expected outcome. The exact formula
is disclosed (CLAUDE.md rule 3). Hand-reasoned: a symmetric `[0,50,100]` game -> 50; a `[0,0,100]`
majority -> modal 0 and a forecast pulled below the midpoint.

### D41.4 — correlated sampling: opt-in Gaussian copula, committed structure
`mc/correlated.py` adds an opt-in correlated sampler (`--correlated-sampling` / `correlated=True`).
Independent per-field triangular sampling stays the default and is byte-identical whether or not the
correlated path exists (`test_correlated_never_changes_the_independent_run`). The committed structure
(a fixed modelling choice, not fitted): **salience correlated within coalitions** — actors on the
same side of the weighted median share salience correlation `SALIENCE_RHO = 0.5` through a Gaussian
copula (correlated normals -> normal CDF -> each salience's triangular inverse-CDF), so the marginals
are exactly the independent sampler's while the joint is correlated. The choice is recorded in
`ForecastRecord.sampling`. Nothing correlated is sealed this session, so `verify` (which re-solves
engine v1 independent) is never asked to reproduce a correlated record; that limitation is noted.

### D41.5 — the DEU gate: all four ship exploratory, an honest negative result
Scored once on the committed TEST split (sourced capability, bootstrap seed 20260721), against the
compromise mean: **challenge-qre 24.63 vs 21.09 (Δ +3.54), pce 20.43 vs 21.09 (Δ −0.66, CI [−2.26,
+1.00]), nash 46.59 vs 21.26 (Δ +25.33), nash-ks 32.41 vs 21.26 (Δ +11.16).** PCE is the only near
miss — a lower point MAE than the compromise mean, but its 95% CI straddles zero, so under the
two-part gate it does **not** validate. No solver clears the gate; each ships as an EXPLORATORY
`--solver` option, none sealed against a live forecast — exactly as gravity/regime did, and exactly
as the oracle ceiling (D11.0: the mean is at the extractable-signal ceiling on DEU) predicted. The
living leaderboard in `BACKTEST.md` gains a Phase C section beside the R1 candidates; the R1 rows are
byte-unchanged. Tests: `tests/test_phase_c_solvers.py` (10), `tests/test_correlated_sampling.py` (6).
The D39.2 regression gate passes untouched.

### D41.6 — QRE live diagnostic on ranged games (dated 2026-07-24): the lock persists
A read-only, pre-resolution diagnostic — no engine code, no sealed record, nothing graded (USIRAN
resolves 2026-08-31, IAEA 2026-09). Ran `--solver challenge-qre` (lambda = 1.0) against the challenge
model on the two live formalized drafts (gitignored `analyses/`), 10,000 draws, seed 42. The QRE
tornado was computed by the same one-at-a-time low/high vary the challenge tornado uses, solved with
`run_qre` (a throwaway script; the committed engine is untouched).

| game | ranged params | zero-swing rows (chal → qre) | mode-vs-MC gap (chal → qre) | CI80 width (chal → qre) |
|---|---|---|---|---|
| Q-2026-USIRAN-STAGE2 (9 actors) | 27 | 18/27 → 17/27 | +7.41 → −0.74 | 44.65 → 25.02 |
| Q-2026-IAEA-SEP (7 actors) | 20 | 13/20 → 13/20 | +10.84 → +9.18 | 32.71 → 22.28 |

**Plainly: QRE does not reduce the degenerate median lock on these live ranged games.** The zero-swing
sensitivity count is essentially unchanged (18→17 of 27; 13→13 of 20) — most single-parameter moves
still fail to shift the weighted median under QRE, which is the lock (D12.3). If anything the soft
partial acceptance makes the ensemble *tighter*, not looser: CI80 narrows on both games (44.65→25.02,
32.71→22.28) and the mode-game/MC gap shrinks (to near zero on USIRAN). So the softening damps
excursions rather than freeing the pinned median. This matches D41.1's fixture finding and points to
the lock being structural — the weighted median is pinned by the capability×salience weight
distribution, not by the hard argmax of offer selection — so quantal response on the acceptance step
does not dislodge it. The compromise mean remains the settlement model; nothing here changes a sealed
number.

### D42.0 — Phase C evidence: E-tags for the eight-method tournament and the median-lock probe
The paper revision keeps the standing rule that every cited number is computed, never hand-typed
(D14.1). Four Phase C leaderboard tags (`E-PHASEC-challenge-qre`, `-pce`, `-nash`, `-nash-ks`) are
emitted by `paper.evidence` from the same `run_successor_search` report that writes BACKTEST.md, each
value carrying the whole verdict (TEST MAE vs compromise, Δ, CI) so the draft cites it entire.
`E-PHASEC-COUNT` computes the number of distinct solution concepts weighed against the mean as
`2 + len(candidates) + len(structural) = 8`. The live median-lock diagnostic is E-tagged too
(`E-QRE-ZEROSWING-{usiran,iaea}`, `E-QRE-CI80-{usiran,iaea}`): `paper.evidence` recomputes it on the
two gitignored formalized drafts at the **same seed (42) and 10,000 draws** the dated D41.6 note used,
so the tags reproduce it byte-for-byte (18/27→17/27, 44.65→25.02; 13/20→13/20, 32.71→22.28). Like the
DEU-derived tags these are skipped on CI when the data is absent (the `--check` data-absent path), so
the gate stays green offline. A reusable `qre_tornado` was added to `mc/sensitivity.py` — the same
one-at-a-time sweep as `tornado`, solved with `run_qre`; additive, the challenge and compromise
numerical paths are untouched and the D39.2 gate stays green.

### D42.1 — Phase C prose: the eight-method report, the operator diagnosis, the broadened ceiling
Section 4 now reports all eight solution concepts against the compromise mean, grouped by tradition:
expected-utility bargaining, its quantal-response softening, the two axiomatic bargaining solutions
(Nash, Kalai-Smorodinsky), probabilistic Condorcet (KTAB's method), and the two fitted structural
blends — with PCE reported honestly as the near-miss that is nominally better yet statistically
indistinguishable (CI straddles zero). A new subsection **4.1, "The operator, not the dynamics,"**
files the operator diagnosis: quantal response softens precisely the discrete acceptance step, yet
leaves the count of dead sensitivity parameters near-unchanged and *tightens* the forecast interval
rather than widening it — so the median lock is a property of the weighted-median operator, not of the
bargaining dynamics above it, with the corollary that the continuous smoothing which cures it is the
weighted mean itself. Section 5's ceiling claim is strengthened to rest on two independent lines of
evidence meeting at the same floor: the noise-floor oracle from above, and the eight-concept
tournament from the side. `paper-assemble` re-run deterministically: 7,079 words, no unresolved
E-tags. E-TESTS refreshed and docs rebuilt; nothing sealed changed.

### D43.0 — Consolidation session: preprint package, outreach draft, STATUS.md (no engine change)
A read-mostly consolidation before submission; no solver, Monte-Carlo, or sealed record was touched.
(a) Printed Section 4 (the successor search, including the new §4.1 operator diagnosis) verbatim from
HEAD for line-by-line review. (b) Built `paper/preprint/`: `manuscript.md` is the assembled
`paper/DRAFT.md` with a title/author/date block prepended — regenerated from the artifact, no new
manuscript prose — plus the four figures copied in; `ssrn-metadata.md` holds the SSRN form fields
(title, author, abstract, keywords) and a 150-word plain-language summary, the only newly-written
prose, which paraphrases the committed abstract and introduces no claim not already in the paper.
(c) Wrote `docs/outreach/scholz-email.md`: the final peer-register email to J. B. Scholz, its claims
updated to the eight-method tournament result, held as a DRAFT (not sent) with a factual, verify-first
pointer to where he can be found. (d) Produced `STATUS.md` at the repo root — one page from artifacts:
engine (v1, six models, tests green), the 14-record sealed ledger with resolution/grading dates (0
graded — all resolve in the future), the case library, the concept canon, the paper, the site, and
every open gate with its threshold; it ends with a **BLOCKED ON HASSAN** list containing only the
human-only steps, in deadline order — the three question gradings (2026-08-06 / 08-31 / 09-30), the
author surname, the SSRN upload, sending the Scholz email, and acquiring the paywalled coercive tables.
E-TESTS unchanged; docs rebuilt for the decisions count. Nothing sealed changed.
