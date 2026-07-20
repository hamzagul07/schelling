# Schelling

An open, continuously-audited strategic forecasting engine: bounded geopolitical
questions → formal bargaining games → deterministic solutions → probability forecasts
with complete audit trails. The open-source successor to Policon / the Bueno de Mesquita
(BDM) expected-utility model.

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
