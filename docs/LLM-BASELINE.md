# The LLM judgment baseline (`llm-judgment`)

`schelling llm-forecast <game-or-draft.json>` gives a model the **same** situation text, sources, and
0–100 continuum the solver received, and asks it directly for a settlement point, an 80% interval,
and — when the rubric is banded — a probability per band. **No solver, no game math.** It samples the
model `n=5` times independently; the headline is the *median* of the sampled points and the *spread*
across samples is reported as its self-consistency. See `src/schelling/llm_forecast/` and D27.

## It is a baseline, not a forecast

The `LLMForecastRecord` is **non-deterministic by nature** — re-running produces different samples.
There is therefore no reproducibility claim; the commitment is the **SHA-256 of the record file**, which
`schelling seal` records exactly as for a solver forecast. A sealed row is labelled `llm-judgment`, and
the same rubric requirement applies: a judgment that cannot be graded by a pre-registered rule is not
sealed.

## The pre-registered comparison, and why it waits

`schelling compare` computes `|median − actual|` across the three families — **challenge**,
**compromise**, and **llm-judgment** — on the live ledger. It is **exploratory until at least 10 graded
questions**: no verdict is claimed, and the harness *refuses to print a ranking* before the threshold —
the same discipline the coercive reading holds to (D20). This is fixed now, before any question grades.

## Contamination rule — the live sealed ledger is the clean venue

Running `llm-forecast` against **DEU** or the **coercive case library** is flagged
`CONTAMINATION-RISK` and reported **separately** from live results: those datasets are historical, and
the model may already know their outcomes, so a good score there proves nothing about forecasting
skill. **The live sealed ledger — questions sealed before they resolve — is the clean venue**, and it
is the only venue `schelling compare` ranks over. Contamination-risk runs never reach it by
construction.
