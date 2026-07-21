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
