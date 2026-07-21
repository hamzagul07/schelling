# AUDIT-2026-07 — Explained in Detail

**Companion to [`AUDIT-2026-07.md`](AUDIT-2026-07.md).** That file is the formal audit: terse, every
claim cited to an artifact, written for a skeptical reviewer. *This* file is the same audit written
out at length — each finding explained in plain language, with the concepts defined and the reasoning
spelled out, for a reader who is new to the project. No new claims are made here; everything traces to
the formal audit and the artifacts it cites. Facts are as of the audit run (HEAD `0c2e6fa`,
2026-07-22); this explainer was written just after, alongside it.

---

## 0. How to read this document

The formal audit answers *"is each claim true, and where's the proof?"* This document answers
*"what does that actually mean, and why should I care?"* If you want the receipts, read the formal
audit. If you want to understand the state of the project, read this. A glossary of the technical
terms is at the end (§9).

---

## 1. What Schelling is, in one honest paragraph

Schelling is a from-scratch, open-source rebuild of a famous political-forecasting model — the
**Bueno de Mesquita expected-utility group-decision model**, used inside the CIA in the 1980s under
the name "Policon" and later sold commercially as "Senturion." That model has been influential for
forty years but was never fully published and never had a complete open implementation anyone could
check. Schelling provides one. On top of the core solver it adds: a **Monte-Carlo layer** (running
the model many times to get a distribution, not a single number), a **backtest harness** (scoring the
model against real historical outcomes), an **LLM-based formalizer** (using a language model to turn a
prose situation into structured inputs — but never to produce a probability), and a
**forecast-integrity apparatus** (a tamper-evident ledger of sealed predictions, a verifier, and a
pre-registered grading rule). The guiding principle, enforced throughout, is: *the language model
structures the problem; the deterministic math produces every number.*

The single most important context for judging any of this: **the entire project is about one day
old.** Its git history is 109 commits over ~25 hours, all by one person. Everything below should be
read against that fact — it is a serious, rigorously built prototype, not a battle-tested system.

---

## 2. Capability inventory — what actually works

### The test suite

Running the full test suite fresh gives **279 tests passing, none failing, none skipped, in about 41
seconds.** Why this matters: a test suite is the project's own claim about what it does correctly.
279 passing tests that run in well under a minute means the claims are (a) numerous and (b) cheap to
re-check — anyone can run them. "None skipped" matters because skipped tests are a common way to hide
broken functionality; here the only conditional-skip guards are for a dataset that isn't shipped in
the repo (it's downloaded separately), and since that data was present, every guard's tests actually
ran. The same four checks (formatting, linting, type-checking, tests) run automatically on every push
via CI, so the bar can't silently slip.

### How much code, and where

There are about **8,900 lines of source code and 3,600 lines of tests** — a healthy roughly 1:2.5
test-to-code ratio for research software. The code is cleanly divided by concern. The biggest pieces
are the backtest harness (~2,200 lines — the machinery that scores the model against data), the CLI
(~1,000 lines), the report renderer (~970), the paper-generation tooling (~930), the LLM formalizer
(~925), and the solver itself (~810). One package, `calibrate/`, is **empty** — a single-line
placeholder file, an intention that was never built. That's harmless but worth noting: it's a stub.

### The commands

The project exposes thirteen command-line surfaces. **Eleven were run against real fixtures during
the audit and all worked:** solving a game, rendering a report, giving lever-finding advice, building
and searching the knowledge index, running the DEU backtest, running the coercive head-to-head,
verifying a sealed forecast, sealing a forecast (which now produced a *real* OpenTimestamps proof),
and both paper-generation commands. **Two were not run:** `analyze` and `formalize`. These are the
only commands that call a paid external AI service (the Anthropic API) over the network, and no API
key was loaded into the audit session. They exist and their help text works, but they are only tested
in the codebase using *replayed* canned responses — never against the live service, not even in CI.
So the two most user-facing entry points have the least end-to-end coverage. That's a real gap, not a
nitpick: a first-time user is most likely to reach for `analyze`, which is exactly the path the
automated tests never exercise for real.

---

## 3. Scientific record — the model's honesty about its own failures

This is the project's strongest feature, and it's a counter-intuitive one: **the model mostly loses,
and the project says so plainly and reproducibly.** Here's what each pre-registered test ("gate")
actually checked and what happened.

- **The replication gate (PASSED).** Before trusting a rebuild, you prove it reproduces a known
  published result. Schelling reproduces the reference case at a settlement value of **9.530**,
  matching the published figure. This is the foundation: it shows the rebuild is faithful to the
  original model, not a different model that happens to look similar.

- **The Session-9 gate (FAILED).** The first real test asked: does the sophisticated bargaining model
  beat two dead-simple baselines (a weighted average of positions, and the middle position) at
  predicting real EU legislative outcomes? It lost — the model scored an average error of **28.31**
  while the simple weighted average scored **23.64** (lower is better). Losing to a weighted average
  is embarrassing for a complex model, and the project reports it without softening.

- **The "fair fight" gate (FAILED again).** A skeptic could object that the first test handicapped the
  model by giving every actor equal power. So the project rebuilt the inputs properly — real
  treaty-based voting weights as each actor's "capability," plus a "reference point" (the status quo
  the negotiation starts from) — and re-ran with the pass/fail rule fixed *in advance*. The fully
  equipped model scored **26.83**; the equally equipped weighted average scored **22.99**. It closed
  some of the gap but still lost. The project even split the data in half, tuned on one half, and
  scored on the untouched other half (**26.07** vs **23.32**) to prove this wasn't just overfitting.
  It wasn't. The model genuinely loses.

- **The successor search (both candidates FAILED).** Having established the model loses, the project
  tried to *build* something that beats the weighted average — two new candidate models motivated by
  the original's specific failure modes. Both lost on held-out data (22.09 vs 21.26; 21.57 vs 21.09),
  with confidence intervals straddling zero (meaning: not distinguishable from the baseline, and
  certainly not better). One of the two candidates, given freedom to weight three ingredients, put
  ~5/6 of its weight on the weighted-average ingredient — it *rediscovered* the baseline it was built
  to beat.

- **The noise-floor oracle (the ceiling result).** The final question: is *any* model losing to the
  weighted average, or is the weighted average simply extracting all the signal there is? The project
  built a deliberately flexible, cross-validated model — one allowed to use far more information — and
  it *still* couldn't beat the weighted average (23.84 vs 22.99; a gap of **−0.84**, i.e. the flexible
  model was actually slightly worse). Interpretation: on this dataset, the weighted average sits at
  the **extractable-signal ceiling**. There's essentially no predictive signal left to capture, which
  is *why* every model failed. This is a genuine scientific finding, and a satisfying one: it turns a
  string of failures into a single explanation.

**Why the pre-registration is trustworthy.** A common way to cheat at this kind of research is to
decide the test *after* seeing the results. The project prevents this using git itself: the exact
train/test data split was committed to version control (`3294081`) *before* any candidate-model code
existed (`8ea92b0`), and this ordering is cryptographically checkable (`git merge-base` confirms the
split commit is an ancestor of the model commit). The commit history *is* the proof that the test
wasn't rigged.

**The reproducibility check.** The audit re-ran the command that regenerates every number in the
project's manuscript and compared it to the committed version. **Every scientific number came out
byte-for-byte identical** — the replication value, all the error scores, the ceiling gap, the
confidence intervals, and the four sealed forecast values. Only two things differed, and neither is a
scientific result: the count of tests (267 in the committed file vs 279 today, because more tests were
added since) and four internal "provenance" hashes (which point to the last commit that touched each
source file, and legitimately changed when those files were edited). The practical takeaway: the
manuscript's numbers are genuinely reproducible, but the committed evidence file is slightly
out-of-date and should be regenerated (see §5, debt item 6).

---

## 4. Integrity audit — the two problems worth losing sleep over

This section is the heart of the audit. The project's most distinctive claim is that its forecasts are
*tamper-evident*: sealed before the outcome is known, and checkable by any outsider. The audit tested
that claim hard, and found two real problems.

### Background: how the "sealing" is supposed to work

When Schelling makes a forecast about a future event, it writes a record file and then computes that
file's **SHA-256 hash** — a 64-character fingerprint that changes completely if even one byte of the
file changes. That fingerprint is published in `FORECASTS.md` *before* the event resolves. The record
file itself is kept private (not committed to git). The idea: after the event happens, anyone can be
handed the record, recompute its fingerprint, and confirm it matches the one published in advance —
proving the prediction wasn't edited after the fact. This is called **commit-reveal**. The project
also ships a `verify` command that runs three checks on a sealed record: (1) is its fingerprint in the
ledger? (2) does its internal "content address" recompute correctly? (3) if you re-run the model from
the record's own saved inputs, do you get the same forecast back? All four sealed US-Iran forecasts
were tested.

### Finding 1: one of the four sealed forecasts fails the project's own `verify` command

Three of the four records pass all three checks cleanly. **The fourth — the "v1 challenge" forecast —
fails.** Specifically, it passes the fingerprint-in-ledger check (its sealed bytes are intact) and
passes the re-run check (re-running the model reproduces the forecast, 34.576, exactly). But it
**fails the middle check**: the "content address" stored inside the record (`45d931c6cd91…`) doesn't
match what you get by recomputing it from the record's own saved inputs (`2cbb0bc624f3…`).

What's going on: that "content address" is a hash of the model's inputs, used as a label. The recompute
`2cbb0bc624f3…` happens to be *exactly* the label on the v1 *compromise* record — which makes sense,
because both v1 records were built from the same underlying game, and this particular hash ignores
which model was used. So the inputs embedded in the failing record are fine; what's stale is the
*label* the record carries. The most likely reason (this part is a hypothesis, flagged as unverified):
the recipe for computing that label changed slightly at some point after this record was created — for
example when a "reference point" setting was added to the model's configuration — and this one old
record was never regenerated to pick up the new recipe. The record created later (v1 compromise) has
the new-style label; the older one kept the old-style label.

**Why this matters even though the forecast is fine.** The number is real and reproducible; nothing
was faked. But the project's headline invitation is *"don't trust us — run `verify` yourself."* The
first skeptic who accepts that invitation and runs `verify` on all four forecasts gets a **FAILED** on
one of them. The damage is to credibility, not to the science — but for a project whose entire selling
point is auditability, a self-audit that fails on a flagship artifact is a headline, not a footnote.
And it needs fixing *before* the September grading, because the sealed bytes can't be changed after the
fact without breaking the seal.

### Finding 2: the "cannot be backdated" guarantee isn't actually in place yet

The project claims its ledger is anchored with **OpenTimestamps** — a service that embeds a
fingerprint into the Bitcoin blockchain, producing proof that a file existed at a certain time that
*no one, including the project's author, can backdate.* This closes a subtle loophole: git history
alone can, in principle, be rewritten, so "I committed this before the event" is a weaker claim than
"the Bitcoin blockchain witnessed this before the event."

The audit checked the `ledger-proofs/` folder, which is supposed to hold these proofs. **It contains
only a README — there is no proof for the actual `FORECASTS.md`.** The reason is chronological: the
four forecasts were sealed in an earlier work session, *before* the OpenTimestamps feature was built,
and the ledger was never re-stamped afterward. The audit confirmed the feature *works* — sealing a
test ledger produced a genuine Bitcoin-anchored proof in about six seconds — but it has never been run
on the file that matters. So today, the four real forecasts rest on git history alone for their
timing. Like Finding 1, this is fixable now and *only* now: after the event resolves, you can no
longer prove you committed to a prediction beforehand.

### The one piece of the integrity story that is fully in order

The **grading rubric** — the rule that says exactly how the forecasts will be scored once the event
happens — is committed, dated before the event, machine-checkable against its schema, and its seven
scoring bands were verified to cover the entire 0–100 scale with no gaps or overlaps. This is
important because a vague or after-the-fact grading rule is another way to fudge a forecast's
track record. Here it's pinned down in advance and complete.

---

## 5. Gaps and debt, explained — "what breaks if this is never fixed"

The formal audit ranks twelve issues by severity. Here's what each one actually costs:

1. **The failing `verify` (Finding 1).** *Cost:* the credibility of the whole audit-yourself pitch.
2. **No blockchain proof on the real ledger (Finding 2).** *Cost:* the "cannot be backdated" claim is
   currently untrue for the actual forecasts; the window to fix it closes at resolution.
3. **The forecasts aren't graded yet.** Zero of four have been scored; the event is ~6 weeks out. The
   project's single biggest forward-looking promise — a live, honest test of whether the simple model
   beats the complex one *out of sample* — is completely unresolved. *Cost:* the headline claim never
   pays off.
4. **The coercive case library is at 2 of a target 8 cases, and both are the "wrong" kind.** The model
   is designed for coercive international crises (its home turf), but the only test cases so far are
   two domestic-politics cases, and the tool correctly refuses to render a verdict from them. *Cost:*
   the model's actual reason to exist is never tested.
5. **The Japan case is blocked** on a missing source PDF. *Cost:* the library can't grow toward 8.
6. **The manuscript's evidence file is slightly stale** (test count and provenance hashes drifted).
   *Cost:* the "regenerate every number with one command" claim is technically violated on re-run,
   even though no science number moved.
7. **`BACKTEST.md` is fragile.** It's assembled by two different commands, and running one of them
   (`backtest`) silently deletes the section the other (`successor`) maintains — the audit observed
   this directly and had to restore the file. *Cost:* routine regeneration can quietly erase the
   successor-search leaderboard.
8. **An empty stub package** (`calibrate/`). *Cost:* essentially none; it's dead weight and a signal
   of an abandoned plan.
9. **Bus factor of one.** Every one of 109 commits is by a single author; no second person has
   reviewed or reproduced the code. *Cost:* correctness rests entirely on one individual, and the
   open-source license invites reuse the code has no independent voucher for.
10. **The repository is ~1 day old.** *Cost:* words like "living document" and "track record" describe
    something that has had essentially no time to be stress-tested by reality or by other people.
11. **The AI-dependent commands aren't tested end-to-end**, and one optional feature downloads a ~2 GB
    model. *Cost:* the most user-facing paths have the least real-world testing.
12. **Type-checking is blind at third-party boundaries** (a few external libraries have no type
    stubs). *Cost:* strong internal type safety, weaker at the seams.

---

## 6. Comparative standing — what's genuinely rare vs. what's just a promise

The audit is careful to keep two lists apart, because blurring them is how projects oversell.

**Genuinely rare and verifiable *today*:**
- A complete, open, deterministic implementation of a model that — by the manuscript's own
  related-work review — has never had one publicly. This is the real contribution, and it's provable
  now (it reproduces the reference case).
- An unusual forecast-integrity toolkit (sealed ledger, one-command verifier, pre-registered rubric,
  blockchain anchoring). The *design* is real and the commands run — with the two caveats from §4.
- Pre-registration you can check with git itself.
- A clean, reproducible negative result about a predictability ceiling.

**Claimed strengths that are UNPROVEN until September 1 or until 8 cases exist** (and must not be
confused with the above):
- That the model is actually useful out-of-sample — the ledger is sealed but ungraded.
- That the model works in coercive settings — its designed purpose — which currently rests on two
  out-of-domain cases and no verdict.
- That the anchoring guarantee holds for the real forecasts — true in design, but no proof exists yet.
- Any notion of a "track record" — there have been zero graded cycles.

The honest one-line summary: **the engineering and the reproducibility are real now; the forecasting
value is a well-constructed promise that hasn't come due.**

---

## 7. The grades, explained

| Criterion | Grade | Plain-language reason |
|---|:--:|---|
| Engineering quality | 8.5/10 | Lots of passing tests, strict type-checking, automated CI, clean structure, almost no shortcuts left in the code — minor marks off for one dead package and a self-clobbering doc. |
| Scientific rigor | 8.5/10 | Tests fixed in advance, cheating prevented by git, failures reported honestly, and a real ceiling finding — held back only by having tested one dataset in one domain. |
| Reproducibility | 9.0/10 | Same inputs always give the same bytes; every manuscript number regenerates identically; the highest-scoring dimension, docked only for a stale evidence file and data you must fetch yourself. |
| Integrity/security | 6.5/10 | The design is excellent but the practice isn't clean: one sealed record fails the project's own verifier, and the real ledger has no blockchain proof. |
| Documentation | 8.0/10 | Unusually thorough and self-critical (a 1,000-line decisions log, plus README, backtest, forecasts, grading, and a full paper) — minor marks off for drift. |
| Product readiness | 5.0/10 | Fine for the author; rough for an outsider — headline commands need a paid key, one feature needs a 2 GB download, the benchmark data isn't included, and there's no packaged release. |
| Present analytical power | 5.5/10 | It reliably produces auditable numbers, but its one tested finding is that its flagship model *loses* to a trivial baseline, and its intended strength is unproven. |
| **Overall** | **7.5/10** | A rigorous, exceptionally reproducible, unusually honest research instrument — held back by being one day old, by a core thesis that hasn't been graded yet, and by one live integrity flaw. |

---

## 8. The three highest-leverage fixes, explained

1. **Make the integrity apparatus clean in practice.** Fix the one record so `verify` passes on all
   four, and generate a real blockchain proof for the actual ledger file. This directly raises the
   lowest grade (integrity) and repairs the project's central selling point. **Time-critical:** both
   must be done before the September resolution, because neither can be retrofitted afterward.
2. **Build the coercive case library to 8 real cases — or openly drop the coercive claim.** This is
   the model's designed purpose and the paper's central open question. Right now it's two cases of the
   wrong kind. Either give the model its fair test on its home turf, or stop implying it has one.
3. **Grade the sealed forecasts on September 1 and regenerate the evidence file.** This is the moment
   the whole live-forecasting story either pays off or honestly doesn't — and it simultaneously
   fixes the stale-evidence debt. It converts the biggest promise into a result.

---

## 9. Glossary

- **BDM / Bueno de Mesquita model:** the expected-utility group-decision forecasting model this
  project rebuilds; actors with positions, salience (how much they care), and capability (power)
  bargain toward a predicted outcome on a 0–100 scale.
- **Deterministic / byte-identical:** given the same inputs and the same random seed, the software
  produces exactly the same output every time, down to the byte — so anyone can reproduce it.
- **SHA-256 hash:** a fixed-length fingerprint of a file; changing any byte changes the fingerprint
  completely. Used to prove a file hasn't been altered.
- **inputs_hash / content address:** a hash of a run's inputs, used as an internal label. Finding 1 is
  about this label being stale on one record.
- **Commit-reveal:** publish a fingerprint of a prediction *before* the outcome is known, reveal the
  full prediction after — proving it wasn't changed in between.
- **OpenTimestamps:** a service that anchors a file's fingerprint in the Bitcoin blockchain, providing
  proof-of-existence-by-a-certain-time that cannot be backdated.
- **Pre-registration:** committing to your experiment's design (here, the data split) *before* seeing
  results, so you can't tailor the test to the outcome. Provable here via git commit order.
- **Held-out / out-of-sample:** data the model was never tuned on; the honest way to measure real
  predictive skill.
- **Weighted mean baseline ("compromise model"):** the dead-simple benchmark — an
  influence-and-salience-weighted average of actor positions — that the sophisticated model keeps
  failing to beat.
- **Noise-floor oracle / extractable-signal ceiling:** a deliberately flexible model used to estimate
  the best score *any* model could get from the available information; if the simple baseline matches
  it, there's no more signal to extract.
- **Bus factor:** how many people would have to be hit by a bus before the project stalls. Here it's
  one.

---

*This explainer changes no code, data, or results — it only restates the committed audit
([`AUDIT-2026-07.md`](AUDIT-2026-07.md)) in fuller language.*
