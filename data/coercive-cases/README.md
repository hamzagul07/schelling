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

## Registered cases

- `ktab-china-2014.json` — Efird, Lester & Wise (2016), *Analyzing Coalitions in China's Policy
  Formulation*, J. East Asian Studies 16, doi:10.1017/jea.2015.4. Two domestic-elite-bargaining
  cases (KTAB SMP study). **`draft-1`, `verified: false`** — outcomes are Claude-proposed and every
  number must be checked against the source PDF before this counts for anything.
