# Coercive / out-of-domain case library — schema

Hand-transcribed, expert-coded stakeholder tables from the BDM/Policon/KTAB lineage with known
outcomes, for the pre-registered head-to-head (`schelling coercive`): challenge (real inputs) vs the
compromise mean vs the fitted successors (gravity/regime). The goal is the **coercive interstate
classics** (Hong Kong 1985, Iran 1984, Feder cases) — see `DECISIONS.md` D11.1. Domestic/cooperative
cases are welcome as out-of-domain validation but are flagged and never counted toward a coercive
verdict.

**No verdict is claimed** by the harness while the library is tiny (N < 15), any transcription is
`verified: false`, or any case is out of the coercive domain. Those caveats are surfaced in the run
note automatically.

## File format

One JSON file per source (`<slug>.json`) in this directory. The loader reads every `*.json` here.

```json
{
  "library_version": "draft-1",
  "transcription": {
    "status": "human-readable provenance / TODO note",
    "verified": false,          // flip to true only after every number is checked against the source
    "verification_method": "blind dual machine transcription + human ratification of judgments",
    "verification_note": "what the blind diff found + the quoted human ratification once given",
    "source_pdf": "url or path to the source"
  },
  "cases": [ { …case… } ],
  "notes": [ "free-text caveats — e.g. domain, horizon rule, bonus columns" ]
}
```

### The verification protocol (`verification_method`)

Every case file is verified by **blind dual machine transcription + human ratification of
judgments**:

1. **Blind dual entry.** The stakeholder table is transcribed twice, independently, from rendered
   images of the source PDF — by two agents that never see the existing JSON. The two
   transcriptions are diffed against each other, then against the JSON. Where the source prints a
   derived `Exercised Power = Influence × Salience / 100` column, it is used as a per-row checksum.
   The `Influence` column maps to the JSON's `capability`.
2. **Human ratification of judgments.** Transcribing the numbers is mechanical; the *interpretive*
   choices are not — outcome codings, the continuum wording, and the horizon rule. These are put to
   Hassan as explicit yes/no questions and are **his call, never the machine's**.

`transcription.verified` flips to `true` **only after Hassan ratifies the judgment questions**, and
his ratification is quoted verbatim in `verification_note`. Until then it stays `false` **even when
the numeric diff is clean** — a perfect transcription of the numbers does not settle the judgments.
`verified` is Hassan's flag alone.

### A case

| field | type | meaning |
|---|---|---|
| `case_id` | string | unique id (becomes the game `question_id`) |
| `title` | string | short description |
| `domain` | string | `coercive_interstate` counts toward the coercive gate; anything else (e.g. `domestic_elite_bargaining`) is out-of-domain and flagged |
| `ex_ante` | bool | was the coding done **before** the outcome was known? |
| `data_collected` | string | when the expert table was coded (becomes `frozen_at`) |
| `source` | string | full citation (paper, table, page) |
| `continuum` | object | `{ "label", "anchor_0", "anchor_100", "markers": { "<value>": "meaning" } }` — 0–100 scale |
| `actors` | array | each `{ "id", "name", "position", "salience", "capability" }`, all on **0–100** |
| `published_model_forecast` | object | optional `{ "model", "value_note" }` — the incumbent model's forecast, for context |
| `outcomes` | object | dated readings, keyed by horizon; each `{ "proposed_value", "range": [lo,hi], "basis", "verified" }` |

### Outcomes and the horizon rule

`outcomes` may hold several dated readings. Exactly one is the **primary** reading that the harness
scores — either flagged `"primary": true`, or, by convention, **the first one listed**. Use the
source's own stated forecast horizon as primary; later readings (e.g. a 5-year outcome) are recorded
and reported but not scored.

### Values

All of `position`, `salience`, `capability`, and every outcome `proposed_value` are on a **0–100**
continuum. Capability is relative influence/clout (strongest actor ≈ 100). Positions map onto the
case's own continuum (`anchor_0` = 0, `anchor_100` = 100).

## MT-1.0 coding flags (`coding_flags`) — for the model-three reading

Optional per case. Present **only** for cases coded for the pre-registered Model Three / Asabiyyah
reading ([`specs/MT-1.0.md`](../../specs/MT-1.0.md) §5). Flags are coded **ex ante**, under the same
blind dual-entry protocol, **with a citation per flag**, and **sealed with the case's verification —
before any model run**. `reference_point` (rp) already lives at the case level; the block adds the
other MT inputs:

```json
"coding_flags": {
  "case": {
    "horizon_months": { "value": 24, "citation": "source, p.N" },
    "vulnerability":   { "value": 1,  "citation": "settlement terms; canon D1" },
    "guarantor":       { "value": 0,  "citation": "no committed third party" }
  },
  "actors": {
    "<actor_id>": {
      "cohesion":   { "value": "exceptional", "citation": "canon B3 observables" },
      "endurance":  { "value": "hardened",    "citation": "canon D2 sacred stakes" },
      "loss":       { "value": 1,             "citation": "actor's own loss framing; canon A3" },
      "perception": { "value": "ledger",      "citation": "itemized-grievance hostility; canon E2" }
    }
  }
}
```

| flag | scope | values | coding rule (MT-1.0 §5) |
|---|---|---|---|
| `cohesion` (h) | actor | `fractured` / `baseline` / `exceptional` | canon B3 observables; `exceptional`/`fractured` each need positive evidence; silence → `baseline` |
| `endurance` (e) | actor | `hardened` / `comfortable` | comfort proxies (wealth, casualty insulation, accountability); sacred-stakes framing (canon D2) forces `hardened` |
| `loss` (L) | actor | `0` / `1` | the actor's own framing of the status quo as intolerable loss (canon A3) |
| `perception` (m) | actor | `ledger` / `lens` / `none` | Grape Trap (canon E2): itemized-grievance hostility → `ledger`, generalized-filter → `lens`; **only principals** are coded |
| `horizon_months` (T) | case | integer months, or omit | the source's stated horizon (library horizon rule) |
| `vulnerability` (V) | case | `0` / `1` | does the contested settlement require the weaker side to accept post-deal vulnerability (canon D1) |
| `guarantor` (G) | case | `0` / `1` | is ≥1 third party with capability **and** stake credibly committed to enforcement (canon D1) |

**Ambiguity default (§5):** an ambiguous flag takes its **null value** and the ambiguity is recorded
on the coding sheet — `cohesion → baseline`, `endurance → comfortable` (hardened only if evidenced),
`loss → 0`, `perception → none`; per case `vulnerability → 0`, `guarantor → 0`, `horizon_months →`
omitted. The loader applies these defaults for any absent flag.

### Coding-sheet template

Fill one row per actor plus the case row, each cell with `value` + `citation`, before sealing:

```
CASE <case_id> — coder: ____  date: ____  (ex ante: sources predate the outcome)
  case:  horizon_months = __ [cite ____]   vulnerability = 0/1 [cite ____]   guarantor = 0/1 [cite ____]
  actor <id>:  cohesion = fractured/baseline/exceptional [cite ____]
               endurance = hardened/comfortable [cite ____]
               loss = 0/1 [cite ____]   perception = ledger/lens/none [cite ____]
  ambiguities recorded: ____________________________________________
```

## Registered cases

- `ktab-china-2014.json` — Efird, Lester & Wise (2016), *Analyzing Coalitions in China's Policy
  Formulation*, J. East Asian Studies 16, doi:10.1017/jea.2015.4. Two domestic-elite-bargaining
  cases (KTAB SMP study). **`draft-1`, `verified: false`** — outcomes are Claude-proposed and every
  number must be checked against the source PDF before this counts for anything.
