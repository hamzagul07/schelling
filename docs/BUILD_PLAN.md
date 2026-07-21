# Schelling — Phase 0 build plan

Working name: **Schelling** (rename anytime). An open, continuously-audited strategic
forecasting engine: bounded geopolitical questions → formal bargaining games → deterministic
solutions → probability forecasts with complete audit trails. The open-source successor to
Policon / the Bueno de Mesquita (BDM) expected-utility model.

**Guiding principle (never violate):** the LLM structures, the math predicts, history
calibrates, everything is logged. No LLM call ever produces a probability.

**Phase 0 scope:** solver + replication test + Monte Carlo + transcript index. Pure Python,
one machine, zero cloud. We do not build ingestion pipelines or the web app until the
Phase 2 ablation gate proves the mechanism earns its keep.

Source documents (keep local copies in `docs/papers/`):
- Feder, "FACTIONS and Policon" (declassified CIA evaluation, 1987):
  https://fm.cnbc.com/applications/cnbc.com/resources/editorialfiles/2021/09/15/Factions_and_Policon_CIA_Report.pdf
- Scholz, Calbert & Smith, "Unravelling Bueno De Mesquita's Group Decision Model" (2011):
  https://www.scitepress.org/papers/2011/31215/31215.pdf
- BDM (1994), "Political forecasting: an expected utility method," in Stokman (ed.),
  *European Community Decision Making*, ch. 4 — contains the worked input table
  (emission-standards case) that becomes our replication fixture.

---

## 1. Ground rules

- Python 3.12, `uv` for env + deps, `pytest`, `ruff`, `mypy --strict` on `src/schelling/solver`.
- License: AGPL-3.0. Public repo from day one (open core).
- Determinism: every stochastic path takes an explicit `seed`; same seed + same inputs =
  byte-identical `ForecastRecord`. This is non-negotiable — auditability starts here.
- The solver is pure: `run(game, config) -> SolverResult`, no I/O, no globals, no network.
- Every run — even a unit test run — emits a complete `ForecastRecord`. Audit culture from
  commit one.
- Commit per milestone. CI (GitHub Actions): ruff + mypy + pytest on every push.

## 2. Repository layout

```
schelling/
├── pyproject.toml
├── LICENSE                      # AGPL-3.0
├── README.md
├── docs/
│   ├── BUILD_PLAN.md            # this file
│   └── papers/                  # Feder + Scholz PDFs, BDM 1994 chapter scan
├── src/schelling/
│   ├── schemas/                 # pydantic v2 models (the data contracts, §3)
│   │   ├── question.py
│   │   ├── stakeholders.py
│   │   └── forecast.py
│   ├── solver/                  # deterministic core (§4)
│   │   ├── model.py             # Solver.run() orchestration
│   │   ├── votes.py             # pairwise contests, weighted mean/median
│   │   ├── expected_utility.py  # EU of challenge/no-challenge terms
│   │   ├── risk.py              # security → risk propensity → exponent
│   │   ├── octants.py           # dyadic relation classification
│   │   ├── rounds.py            # offer exchange + position updating
│   │   └── convergence.py       # stopping rules (our upgrade)
│   ├── mc/                      # Monte Carlo layer (§6)
│   │   ├── sampling.py          # triangular draws from (low, mode, high)
│   │   ├── monte_carlo.py
│   │   └── sensitivity.py       # one-at-a-time tornado
│   ├── knowledge/               # transcript concept index (§7)
│   │   ├── chunker.py
│   │   ├── embed.py             # bge-m3 local
│   │   ├── index.py             # sqlite-vec behind KnowledgeIndex interface
│   │   └── templates.yaml       # game template cards
│   ├── calibrate/               # Phase 2 stub (base-rate blending) — interface only
│   └── cli.py
├── tests/
│   ├── fixtures/
│   │   └── emission_standards.json
│   ├── test_votes.py
│   ├── test_risk.py
│   ├── test_rounds.py
│   ├── test_convergence.py
│   ├── test_replication.py      # THE gate (§5)
│   └── test_mc.py
└── data/
    └── transcripts/             # Jiang transcripts (gitignored)
```

## 3. Data contracts (build these first — everything depends on them)

Pydantic v2 models. Field names are frozen once the replication test is green.

**Actor** — a stakeholder in one game. All three core values live on a 0–100 scale, per
the original Policon input procedure (strongest actor's capability = 100, others
proportional).

```json
{
  "id": "us_admin",
  "name": "US administration",
  "position": {"low": 55, "mode": 62, "high": 70},
  "salience": {"low": 85, "mode": 90, "high": 95},
  "capability": {"low": 95, "mode": 100, "high": 100},
  "evidence": [{"source": "state.gov briefing", "date": "2014-11-20", "note": "red lines restated"}]
}
```

`(low, mode, high)` triangular ranges are our upgrade over Policon's point estimates. A
point estimate is just `low == mode == high`. The replication fixture uses point estimates
(the paper's exact numbers).

**GameSpec** — one formalized situation.

```json
{
  "question_id": "Q-1994-EMISSIONS",
  "frozen_at": "1994-01-01",
  "continuum": {"label": "Year of emission-standard introduction", "anchor_0": "...", "anchor_100": "..."},
  "actors": [ ... ],
  "template": "multilateral_bargaining",
  "horizon": "one_shot",
  "notes": "Replication fixture from BDM 1994 Table 1 via Scholz et al."
}
```

**SolverResult** — one deterministic run: per-round log (positions, offers, octant matrix),
final forecast (weighted median + mean), rounds executed, which stopping rule fired.

**ForecastRecord** — the audit artifact: `question_id`, `run_id`, engine version (git SHA),
`inputs_hash` (SHA-256 of canonical GameSpec JSON), the outcome distribution, CI80,
settlement-point summary, convergence stats, sensitivity table, seed, timestamps. This
schema is the product's spine; design it as if a journalist will read it, because one will.

## 4. Milestone 0.1 — deterministic solver core

Implement the model **directly from Scholz et al. §3–4** (the reconstructed equations),
not from memory or paraphrase. Have the PDF open; paste the relevant subsections into the
Claude Code session when implementing each module. The structure:

1. **Weights.** Effective weight of actor *i*: `w_i = capability_i × salience_i / 100`.
2. **Pairwise contests** (`votes.py`). Votes actor *i* contributes when outcome `x_j` is
   compared against `x_k`: proportional to `w_i × (|x_i − x_k| − |x_i − x_j|) / R` where
   `R` is the continuum range. Sum over actors → who wins each pairwise contest.
3. **Baseline forecasts.** Weighted mean `Σ w_i x_i / Σ w_i` and the **weighted median**
   (the position that defeats every alternative in pairwise contests — the model's
   headline forecast, per the median-voter logic).
4. **Expected utility of challenging** (`expected_utility.py`). For each ordered dyad
   (i, j): probability of success from mobilized third-party votes; utility terms from
   position distances; the no-challenge / status-quo branches. Exact functional forms:
   Scholz §3.
5. **Risk** (`risk.py`). Actor security (distance of own position from the forecast)
   → risk propensity → risk exponent transforming utilities. Exact form: Scholz §3.
6. **Octant classification** (`octants.py`). Each dyad's `(EU_ij, EU_ji)` pair maps to a
   relation type — compel, compromise, capitulate, stalemate, conflict — which determines
   what offer, if any, i makes to j. Exact mapping: Scholz §4.
7. **Rounds** (`rounds.py`). Each round: compute all offers; each actor evaluates offers
   received and moves per the decision rule in the paper (accept the enforceable offer
   requiring least movement, in the paper's terms); positions update; recompute weights →
   contests → EU → octants.
8. **Stopping rule** (`convergence.py`) — **our upgrade**, since Scholz flag the original's
   convergence ambiguity. Stop when (a) the forecast median moves < 0.5 continuum units
   for 2 consecutive rounds, or (b) a hard cap of 20 rounds. Record which rule fired and
   the full per-round trajectory. Never silently truncate.

Where the paper itself is ambiguous (Scholz call several such points out), implement the
interpretation that reproduces their replication, and document the choice in a
`DECISIONS.md` — divergences explained, never hidden.

## 5. Milestone 0.2 — the replication gate

- Transcribe the emission-standards input table (BDM 1994, Table 1, reproduced in Scholz)
  into `tests/fixtures/emission_standards.json`. Transcribe by hand from the PDF; a typo
  here poisons everything downstream, so double-enter and diff.
- `test_replication.py`: run the solver on the fixture; assert the forecast matches the
  paper's reported outcome within ±1.0 continuum units, and that round-count/behavior is
  consistent with what Scholz report.
- **This test is the definition of "the solver exists."** Until it's green, nothing else
  gets built. If it can't be made green, the residual deviation gets quantified and
  explained in `DECISIONS.md` before proceeding — that analysis is itself publishable
  material.

## 6. Milestone 0.3 — Monte Carlo + sensitivity

- `sampling.py`: triangular draws from each `(low, mode, high)`; one draw = one fully
  materialized point-estimate GameSpec.
- `monte_carlo.py`: N draws (default 10,000), each solved deterministically with a derived
  seed; aggregate → outcome distribution, CI80, convergence-rate stats.
- `sensitivity.py`: one-at-a-time tornado — re-solve with each actor-field at `low` and
  `high` holding the rest at `mode`; rank parameters by forecast swing. Output is the
  "what to watch" list (e.g., "flips below 50% only if actor X's position > 45").
- Performance target: 10k draws in under 60s on one machine. Vectorize contests with
  numpy; the round loop can stay plain Python if the math inside is vectorized.
- Reproducibility test: same master seed → identical distribution, twice.

## 7. Milestone 0.4 — transcript concept index

- Input: `data/transcripts/*.txt` (the Prof. Jiang game theory lectures).
- Chunk ≈800 tokens with 15% overlap; embed locally with `bge-m3` (CPU is fine at this
  volume; the DGX Spark makes re-runs instant).
- Store in **sqlite-vec** behind a `KnowledgeIndex.search(query, k)` interface. Phase 0
  has zero infra on purpose; Phase 2 swaps the implementation to pgvector without touching
  callers.
- `templates.yaml`: 10–15 game-template cards — `{name, conditions, solution_concept,
  transcript_refs, notes}` — covering at minimum: prisoner's dilemma, chicken/brinkmanship,
  war of attrition, bargaining with incomplete information, signaling, repeated games,
  commitment problems, coalition/multilateral bargaining. Draft with Claude from the
  transcript chunks, then hand-review each card.
- Acceptance: `schelling knowledge search "war of attrition"` returns the relevant
  transcript passages with source refs.

## 8. CLI

Thin `typer` CLI, two commands for now:

```
schelling solve tests/fixtures/emission_standards.json --draws 10000 --seed 42
schelling knowledge search "commitment problem"
```

`solve` prints the forecast summary and writes the full `ForecastRecord` JSON to `runs/`.

## 9. Phase 0 definition of done

- [ ] `test_replication.py` green (or deviation quantified + explained in DECISIONS.md)
- [ ] 10k Monte Carlo draws < 60s, byte-identical under a fixed seed
- [ ] Sensitivity tornado produced for the replication fixture
- [ ] Transcript index searchable from the CLI
- [ ] Every solve emits a complete ForecastRecord
- [ ] CI green: ruff, mypy --strict (solver), pytest
- [ ] Private personal-analysis edition, AGPL-3.0, README states the guiding principle verbatim

> **Distribution update (Session 5):** this is now a **private, personal-analysis edition**.
> The "open, public repo from day one / open core" framing above and in §1 is superseded:
> public release and the public scoreboard are **deferred** to a later phase. The AGPL-3.0
> license and the guiding principle are unchanged.

## 10. Claude Code session plan

Keep sessions scoped to one milestone; commit at the end of each.

**Session 1 — skeleton + contracts + contests.** "Scaffold the repo per §2 of
docs/BUILD_PLAN.md (uv, pytest, ruff, mypy, AGPL license, CI workflow). Implement the
pydantic schemas from §3 and `votes.py` (weights, pairwise contests, weighted mean and
median) from §4 steps 1–3, with unit tests using a tiny 3-actor toy fixture."

**Session 2 — the model.** Have the Scholz PDF open. "Implement expected_utility.py,
risk.py, octants.py, rounds.py, convergence.py per §4 steps 4–8, taking exact functional
forms from the pasted Scholz sections. Then build the emission-standards fixture and make
test_replication.py pass per §5. Log every interpretive choice in DECISIONS.md."

**Session 3 — uncertainty.** "Implement §6: triangular sampling, the Monte Carlo runner
with derived seeds, the tornado sensitivity, and the performance + reproducibility tests."

**Session 4 — knowledge + CLI.** "Implement §7 (chunker, bge-m3 embedding, sqlite-vec
index, templates.yaml drafting flow) and the §8 CLI. Wire ForecastRecord output."

## 11. Parked for later phases (do not start early)

**Phase 1** — the formalizer: question schema for live cases, the Claude extraction prompt
producing ranged, evidence-cited stakeholder tables, template classification grounded in
the §7 index. **Phase 2** — GDELT via BigQuery, UCDP/ACLED/CoW/ICB ingestion, the ICB
backtest harness (20 resolved crises), and the ablation gate: engine vs. plain-LLM vs.
base rates on identical questions, Brier-scored. The gate decides whether Phase 3 (the
situation room, the public scoreboard, the API) gets built at all.

> **Phase 2 status (Sessions 9–10).** DEU benchmark done: the challenge (BDM) solver loses to a
> capability×salience weighted mean on EU legislative bargaining, even in a fair fight with sourced
> capabilities and a reference point (`BACKTEST.md`, D9–D10). **Scheduled next: the ICB coercive
> benchmark** — coercive interstate crises, the setting the challenge model is actually built for.
> The DEU result alone does not justify a Phase-3 build; ICB is the decisive test.
