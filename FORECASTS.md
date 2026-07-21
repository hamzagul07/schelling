# FORECASTS.md — the sealed forecast ledger

**Commit-reveal.** Each forecast is sealed *before* the event resolves by recording the SHA-256 of
its `runs/` record file — a commitment that cannot be retrofitted after the outcome is known. The
record files themselves are never committed (`runs/` is gitignored), so no number can be quietly
edited after the fact. To reveal and verify after grading, run `sha256sum runs/<file>` locally and
check the digest against the matching line below.

**Resolution date: 2026-08-31** (the real-world event resolves) · **Grading date: 2026-09-01**
(each record is scored as `|forecast median − actual|` on the same 0–100 continuum).

## Q-2026-USIRAN-STAGE2 — Will the US and Iran advance to MOU "stage two" by 31 Aug 2026?

Continuum: shape of a comprehensive US-Iran settlement (0 = maximal US/Israel, 100 = maximal Iran).
Two model families are sealed per vintage: the **challenge** (BDM bargaining) solver and the
**compromise** (capability × salience weighted mean) model — a live, out-of-sample test of the
DEU-backtest verdict that the compromise mean wins.

<!-- LEDGER:START -->
| model | vintage | question | frozen_at | median | sha256 (of the runs/ record file) |
|---|---|---|---|---:|---|
| challenge | v1 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 34.576 | `aece91bdcfd8a35aeea15c98fc6d10af11793fce5a637f9e277f1225a1d1e54f` |
| compromise | v1 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 41.636 | `c87d91ae7f0532966123a78f383fcd6a2403ab1299c7609f3dc496dbbd7b6782` |
| challenge | v2 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 29.407 | `3bc97cd4a4ba53fc1255801154c5775281c72dfaf06bcc632fb91263a3c17372` |
| compromise | v2 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 39.443 | `d55ffc3e78fc5543b5224f6bb925b5793226913f436f9af7b9a8f20511dd12f6` |
<!-- LEDGER:END -->


## Vintages, and the retired Iran-split experiment

- **v1** — the 8-actor game (US, Iran, Israel, `gulf_hawks`, `gulf_moderates`, E3/EU, Russia,
  China/Pakistan). This is the vintage sealed in the Session-10 ledger.
- **v2** — the 9-actor revision: a **single `iran` actor** (the Iran-faction-split experiment was
  retired — see DECISIONS.md D12.2), the **IAEA added** as an actor, and the Gulf blocs renamed
  (`gulf_hawks` → `uae_hawkish_gulf`, `gulf_moderates` → `moderate_gulf`).

**Correction to the earlier ledger (stated explicitly, D12.0).** The previous FORECASTS.md pinned
its two v1 rows by a *partial* `commitment` hash (question + model + inputs_hash + seed + ensemble),
not by the SHA-256 of the record file, and it recorded only v1. This ledger supersedes it: every
line is now the **SHA-256 of the exact `runs/` record file** (recomputed here as the source of
truth), and both vintages are sealed. The forecast medians are unchanged (v1 challenge 34.576, v1
compromise 41.636); only the hash basis was corrected and v2 added.

`schelling seal <record.json> --vintage <label>` appends a line here in one step (idempotent — a
record already sealed is reported and left unchanged).
