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

## CLI

```sh
# Solve a game: Monte Carlo forecast + tornado, writes the ForecastRecord to runs/
schelling solve tests/fixtures/emission_standards.json --draws 10000 --seed 42

# Build the transcript index (bge-m3; downloads the model on first run), then search it
schelling knowledge build --embedder bge-m3
schelling knowledge search "war of attrition" -k 5

# Formalize a described situation into a reviewable draft (needs the `formalize` extra +
# ANTHROPIC_API_KEY). Prints a stakeholder table; NEVER auto-solves — review, then solve.
schelling formalize situation.txt --sources ./sources -o game.draft.json
```

Optional extras: `uv sync --extra knowledge` (bge-m3 embeddings, ~2 GB model) and
`uv sync --extra formalize` (the Claude client). Neither is needed to run the tests.

## Development

This project is managed with [`uv`](https://docs.astral.sh/uv/) and targets Python 3.12.

```sh
uv sync --extra dev      # create the environment
uv run ruff check .      # lint
uv run mypy              # type-check (strict on the solver)
uv run pytest            # tests
```

Every stochastic path takes an explicit `seed`; same seed + same inputs = byte-identical
output. Auditability starts there.

## License

[AGPL-3.0-or-later](LICENSE).
