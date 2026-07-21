# Schelling

A continuously-audited strategic forecasting engine: bounded geopolitical
questions → formal bargaining games → deterministic solutions → probability forecasts
with complete audit trails. A successor to Policon / the Bueno de Mesquita (BDM)
expected-utility model.

> **This is a private, personal-analysis edition.** Public release and the public
> scoreboard are deferred to a later phase; the AGPL-3.0 license still applies.

## Guiding principle (never violate)

> the LLM structures, the math predicts, history calibrates, everything is logged. No LLM
> call ever produces a probability.

## Status

Phase 0 — solver + replication test + Monte Carlo + transcript index. Pure Python, one
machine, zero cloud. See [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) for the full plan and
[`DECISIONS.md`](DECISIONS.md) for every interpretive choice made against the source
papers in [`docs/papers/`](docs/papers/).

**Session 1 (done):** repo scaffold, pydantic v2 data contracts, and the deterministic
vote layer — effective weights, pairwise (Condorcet) contests, weighted mean, and the
weighted-median forecast.

**Session 2 (done):** the full solver — expected utility, risk propensity, octant
classification, offer exchange, and the convergence stopping rule — and the BDM-1994
emission-standards replication gate (`tests/test_replication.py`). The converged median
forecast lands within ±1.0 of the outcome Scholz et al. reproduce; every interpretive
choice against the paper is logged in [`DECISIONS.md`](DECISIONS.md) (D2.x) and the
equation extract is in [`docs/papers/scholz_extract.md`](docs/papers/scholz_extract.md).

**Session 3 (done):** the Monte Carlo + sensitivity layer — triangular sampling, a
seed-derived deterministic MC runner (10,000 draws in ~4 s, vectorized contests), the
one-at-a-time tornado, and full `ForecastRecord` emission to `runs/` (distribution, CI80,
convergence stats, sensitivity, seed, config, inputs hash, engine git SHA). Same master
seed → byte-identical record (D3.x).

**Session 4 (done):** the transcript concept index (§7) — lecture-aware chunking, a
pluggable embedder (bge-m3 in production, a deterministic hashing embedder for tests),
sqlite-vec storage behind `KnowledgeIndex.search`, and 13 hand-reviewable game-template
cards — plus the `schelling` CLI (§8). **This closes Phase 0.**

**Session 5 (done) — Phase 1 formalizer:** `schelling formalize` turns a described
situation into a reviewable `DraftGameSpec` (ranged actors, sourced evidence, template
classification, an explicit assumptions list, and token/cost provenance). The LLM
structures; it never predicts and never auto-solves. A concepts-library firewall enforces
that every real-world claim traces to the supplied text/sources (CLAUDE.md rule 6). Tests
use a record/replay client so CI never calls the live API.

**Session 6 (done) — report renderer:** `schelling report` renders a `DraftGameSpec`
(review sheet), a `ForecastRecord` (full analysis), or an `AdviseRecord` to a single
self-contained HTML file — inline CSS, charts as inline SVG (actor map, outcome histogram,
sensitivity tornado, median trajectory), no JavaScript and no network. Deterministic: same
artifact → byte-identical HTML (D6.x).

**Session 7 (done) — advise mode:** `schelling advise --actor <id>` runs a one-sided lever
search — the actor's own position/salience moves (benefit and cost reported separately) and
a ranked "who to work on" list of feasible shifts of other actors toward the advisor's ideal.
Writes a deterministic `AdviseRecord`; the report carries a standing caveat that opponents are
held to the model's fixed behaviour — lever-finding, not a playbook (D7.x). The position grid is
adaptive (span/20) and persuasion rows are labeled **energize** vs **defuse** (D8.0).

**Session 8 (done) — live search in the formalizer:** `schelling formalize --search` lets the
model run Anthropic's server-side web search before drafting. Everything it fetches is evidence:
each page is recorded in `sources_fetched` `{url, title, retrieved_at, snippet}` and may be cited
in an evidence note like a supplied source, while the concepts index stays banned from factual
fields. A live-searched draft is stamped `frozen_at = today` and marked `live_searched` (it can't
be frozen in the past — so backtests always run with search OFF, CLAUDE.md rule 7). The report
renders the fetched sources as a linked list. Off by default; CI stays offline via replay
fixtures (D8.x).

**Session 9 (done) — the DEU backtest (Phase 2):** `schelling backtest data/deu/` scores the
solver against **351 resolved issues** from the open-access **DEU III** dataset (EU legislative
decision-making; `doi:10.34810/data53`, CC BY 4.0, downloaded into the gitignored `data/deu/`).
It reports MAE for the paper-faithful solver, a risk-off variant, an R×Q sweep, and two naive
baselines (capability×salience weighted mean, median actor position), writes a deterministic
`BacktestRecord` + `BACKTEST.md` + an HTML report, and judges a **gate fixed in advance**: the
solver must beat both baselines. **It does not** — the solver (MAE 28.31) loses to the weighted
mean (23.64), reproducing the canonical DEU finding that a simple weighted mean is hard to beat.
A negative finding, written up honestly in [`BACKTEST.md`](BACKTEST.md) (D9.x).

## CLI

```sh
# Solve a game (a bare GameSpec or a formalizer DraftGameSpec): Monte Carlo forecast +
# tornado, writes the ForecastRecord to runs/. A draft's assumptions and formalize
# provenance are carried through into the record and the report.
schelling solve tests/fixtures/emission_standards.json --draws 10000 --seed 42
schelling solve game.draft.json --draws 10000        # solve a formalizer draft end-to-end

# Build the transcript index (bge-m3; downloads the model on first run), then search it
schelling knowledge build --embedder bge-m3
schelling knowledge search "war of attrition" -k 5

# Formalize a described situation into a reviewable draft (needs the `formalize` extra +
# ANTHROPIC_API_KEY, auto-loaded from a project .env). Prints a stakeholder table; NEVER
# auto-solves — review, then solve. On a concepts-library leak it quarantines the draft.
schelling formalize situation.txt --sources ./sources -o game.draft.json

# ...or let the model search the web first for current sources (recorded in sources_fetched;
# stamps frozen_at = today and marks the draft live-searched). Never use --search for backtests.
schelling formalize situation.txt --search --max-searches 5 -o game.draft.json

# Find levers for one actor: own moves (position/salience) + who to persuade. Writes an
# AdviseRecord to runs/. One-sided search — lever-finding, not a playbook.
schelling advise game.json --actor germany --draws-per-candidate 2000 --target-draws 10000

# Render any artifact (draft, ForecastRecord, AdviseRecord, or BacktestRecord) to a report
schelling report runs/Q-1994-EMISSIONS-mc10000-s42-*.json -o report.html --open

# Backtest the solver + naive baselines against the DEU benchmark (search off; writes BACKTEST.md)
schelling backtest data/deu/ --draws 2000 --seed 42 --html backtest.html
```

The DEU dataset is not redistributed here; download the four open-access DEU III files
(`doi:10.34810/data53`) into `data/deu/` before running the backtest — see [`BACKTEST.md`](BACKTEST.md).

## Development

This project is managed with [`uv`](https://docs.astral.sh/uv/) and targets Python 3.12.

```sh
uv sync --all-extras     # the one install command — full working environment (D7.0)
uv run ruff check .      # lint
uv run mypy              # type-check (strict on the solver)
uv run pytest            # tests
```

**Install with `uv sync --all-extras`.** It installs everything — dev tooling, the
`knowledge` extra (bge-m3 embeddings, ~2 GB model), and the `formalize` extra (the Claude
client) — in one command, so a partial `--extra X` sync can never silently remove another
extra. The tests themselves need only the base + dev deps (they inject lightweight fakes for
bge-m3 and Claude), but `--all-extras` is the standard so the environment is always complete.

Every stochastic path takes an explicit `seed`; same seed + same inputs = byte-identical
output. Auditability starts there.

## License

[AGPL-3.0-or-later](LICENSE).
