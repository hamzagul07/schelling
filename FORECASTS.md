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

**Grading rubric (pre-registered):** [GRADING-Q-2026-USIRAN-STAGE2.md](GRADING-Q-2026-USIRAN-STAGE2.md)
— binary resolution criterion, adjudicating sources, the real-world → 0–100 mapping rule, and the
grading formula, all fixed before resolution (D17.1). New forecasts cannot be sealed without such a
rubric on their question.

<!-- LEDGER:START -->
| model | vintage | question | frozen_at | median | sha256 (of the runs/ record file) |
|---|---|---|---|---:|---|
| challenge | v1 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 34.576 | `aece91bdcfd8a35aeea15c98fc6d10af11793fce5a637f9e277f1225a1d1e54f` |
| compromise | v1 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 41.636 | `c87d91ae7f0532966123a78f383fcd6a2403ab1299c7609f3dc496dbbd7b6782` |
| challenge | v2 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 29.407 | `3bc97cd4a4ba53fc1255801154c5775281c72dfaf06bcc632fb91263a3c17372` |
| compromise | v2 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 39.443 | `d55ffc3e78fc5543b5224f6bb925b5793226913f436f9af7b9a8f20511dd12f6` |
| challenge | v1 | Q-2026-IAEA-SEP | 2026-07-22 | 45.837 | `fc271d2dbd8c7493d9001026ab59c2b937a16eb612c065799e20a615970a2f00` |
| compromise | v1 | Q-2026-IAEA-SEP | 2026-07-22 | 50.518 | `e8d10117192f1259b9e9ab6250641f82e0c1d50a4c00c2e73ff193580f867f99` |
| llm-judgment | v2 | Q-2026-USIRAN-STAGE2 | 2026-07-21 | 41.000 | `180da06528d6a03128e4acde8e12e50432045e4cfb49d783105345bbc92bf2d4` |
| llm-judgment | v1 | Q-2026-IAEA-SEP | 2026-07-22 | 32.000 | `074e17529b416a7b6deabb75b6e8ceccc62be1f6feba061c44b0ee47979f52cf` |
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
record already sealed is reported and left unchanged). It refuses to seal a forecast whose question
carries no pre-registered `resolution_rubric` (D17.1), and on each seal it anchors this ledger with
OpenTimestamps (D17.2).

## Independent verification

Anyone can audit a sealed forecast without trusting us:

1. **Recompute-and-match (`schelling verify <record.json>`).** Recomputes the record file's SHA-256
   and matches it against the table above, recomputes the canonical inputs hash, and re-solves the
   embedded game with the record's own config and seed to confirm the forecast reproduces
   byte-for-byte (determinism, CLAUDE.md rule 2). Reports PASS/FAIL per check. Equivalently, by hand:
   `sha256sum runs/<file>` and compare the digest to the matching row.
2. **External time anchor (OpenTimestamps).** Each seal timestamps this file; the proofs live in
   `ledger-proofs/` (content-addressed by the ledger's SHA-256). To confirm a commitment predates
   resolution, install the client (`pip install opentimestamps-client`), then run
   `ots verify ledger-proofs/FORECASTS.md-<sha12>.ots -f FORECASTS.md` (upgrade first with
   `ots upgrade` once the Bitcoin attestation has confirmed). A Bitcoin-anchored timestamp cannot be
   backdated — not even by us. When the `ots` client is absent at seal time, anchoring is a logged
   no-op and the SHA-256 commitment still stands.

## External anchoring — correction-on-top (D18.2, dated 2026-07-22)

Stated plainly, both facts at once, in the same spirit as the hash-basis correction above:

- The four rows were **sealed on 2026-07-21** (their `frozen_at` dates), recorded in git before the
  event resolves. Those seal *dates* rest on **git history** — the commits that published these
  SHA-256 digests ahead of resolution.
- The OpenTimestamps feature did not exist until 2026-07-22, so the **external Bitcoin anchor on this
  file dates from 2026-07-22, not from the original seal.** The proof in `ledger-proofs/` proves this
  ledger's exact bytes existed by 2026-07-22 — still well before the 2026-08-31 resolution — but it
  does **not** back-date to 2026-07-21.

Neither fact is hidden. Re-anchor at any time with `schelling stamp` (no new seal required); each
distinct ledger state gets its own content-addressed proof.

## Canonicalization epochs and the v1-challenge record (D18.1)

A record's internal content-address (`inputs_hash`) has two epochs. **v1** predates the
`SolverConfig.reference_point` field (added Session 10, D10.4); **v2** (current) includes it. The
v1-challenge record was created under v1, so its stored `inputs_hash` is **`45d931c6cd91…`**;
recomputed under current v2 rules the same game hashes to **`2cbb0bc624f3…`**. The difference is
*exactly* the reference-point field — bisected and confirmed (the v1-challenge record's stored
`solver_config` has no `reference_point` key; dropping that key from the v2 recompute reproduces
`45d931c6cd91` byte-for-byte). **No sealed byte was ever changed.** `schelling verify` is epoch-aware:
it reproduces the stored hash under v1 rules and reports PASS, so all four records verify. Mapping,
for the record: **v1-challenge `45d931c6cd91` (v1) → `2cbb0bc624f3` (v2).**
