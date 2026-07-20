# CLAUDE.md — standing rules for this repository

These rules are non-negotiable. They exist so that a journalist, an auditor, or a future
maintainer can trust every number this engine produces. Read them before writing any code.

## 1. The LLM structures, the math predicts

No LLM call anywhere in this codebase ever produces a probability. LLMs may formalize a
question, extract a stakeholder table, or classify a game template — structuring work only.
Every probability, forecast, and settlement point comes from the deterministic solver and
the Monte Carlo layer. If you find yourself about to have a model *estimate* an outcome,
stop: that number must be *computed*.

## 2. Full determinism

Every stochastic path takes an explicit `seed`. Same seed + same inputs = byte-identical
output (down to the serialized `ForecastRecord`). No implicit clocks, no un-seeded RNGs, no
`set` iteration order leaking into results, no wall-clock timestamps inside hashed content.
Determinism is the foundation of auditability; a non-reproducible run is a bug.

## 3. Equations come from the papers, never from memory

The exact solver equations come from `docs/papers/` — primarily Scholz, Calbert & Smith
(2011), *Unravelling Bueno De Mesquita's Group Decision Model*, cross-checked against the
Feder (1987) CIA evaluation. Never transcribe an equation from memory or paraphrase. Have
the PDF open; paste the relevant subsection into the session when implementing a module.
Every interpretive choice — every point where the paper is ambiguous and we pick one
reading — gets logged in `DECISIONS.md`, with the equation number and page it came from.
Divergences are explained, never hidden.

## 4. One milestone per session

Work is scoped to one milestone (see `docs/BUILD_PLAN.md` §10) and stops there. Never begin
the next plan section unasked. Commit at the end of each milestone.

## 5. Green before commit

Run `ruff`, `mypy`, and `pytest` — all green — before every commit. `mypy` is `--strict` on
`src/schelling/solver`. CI enforces the same three on every push; do not push red.

## 6. The knowledge index is a concepts library ONLY

The knowledge index is a concepts library ONLY. Retrieval may inform which game template
applies and how to reason about structure; it is NEVER a source of facts, actors, payoffs,
capabilities, or evidence about the real world. Every real-world claim in a GameSpec must
trace to user-supplied situation text or sources.
