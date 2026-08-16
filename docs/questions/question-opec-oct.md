# Question package — Q-2026-OPEC-OCT

A fast-resolving ledger question in the OPEC monthly-decision series. Drafted 2026-08-16, before any
forecast is run. **Resolution 2026-09-10 23:59 UTC · Grading 2026-09-11.** The second question in the
series, and the first built on the series scaffolding (see `docs/questions/README.md`).

## Why this question

- **It resolves quickly and arithmetically.** The OPEC+ countries running the additional voluntary
  adjustments meet on 6 September 2026 to set October production. The outcome is a collective
  adjustment in barrels per day, so grading is a linear formula — no bands to argue over.
- **It applies the D28.0 lesson.** Unlike `Q-2026-OPEC-SEP`, whose continuum put the status-quo
  rollover at the midpoint (50), this continuum anchors to the *plausible range* for the decision (a
  150 kb/d cut to a 600 kb/d increase) so the rollover sits at **20** — near a pole, where a mid-scale
  forecast is informative rather than the default a dispersed field produces.
- **Two decimals, not one integer.** At a slope of 0.133 continuum units per kb/d, integer grading
  would flatten ~7.5 kb/d into each step; the rubric grades to the hundredth (D57.1).
- **A reference class exists.** The OPEC monthly-decision series has a pre-registered sessions-at-risk
  denominator (`docs/questions/opec-reference-class.md`) — currently **INCOMPLETE and unratified**, so
  it does not feed this question until a human ratifies it.
- **A graded sibling exists.** `Q-2026-OPEC-SEP` is graded (+188 kb/d → 66 on its scale), so this
  question extends a live, scored series against the same real bargaining forum.

## Context established from sources, 2026-08-16

The additional-voluntary-adjustment group is now **seven countries** — Saudi Arabia, Russia, Iraq,
Kuwait, Kazakhstan, Algeria and Oman — after the UAE left OPEC/OPEC+ effective 1 May 2026. Through
2025 the group unwound its 2.2 mb/d tranche (monthly increases of 138→411→548→547 kb/d, Apr–Sep
2025), then began unwinding the 1.65 mb/d tranche (announced April 2023) with smaller ~137 kb/d
steps (Oct–Dec 2025), **paused increments through Q1 2026** for seasonality, resumed at +206 kb/d
(April–May 2026), and has settled into a **+188 kb/d monthly cadence** (June, July, August and
September 2026 — the last being the graded `Q-2026-OPEC-SEP` outcome). The group holds monthly
meetings and reiterates that increases may be paused or reversed as conditions change; production
during the maximum-sustainable-capacity assessment window bears on 2027 baselines. See the sourced
enumeration and citations in `docs/questions/opec-reference-class.md`.

Note for the drafter: prefer the OPEC Secretariat's own statement over aggregators; opec.org is
bot-blocked to the archive fetcher but its `pr-detail` statements are reachable one at a time.

## situation.txt (paste-ready)

    QUESTION Q-2026-OPEC-OCT

    What collective crude production adjustment will the OPEC+ countries participating in the
    additional voluntary adjustments announce for October 2026, at their meeting scheduled for
    6 September 2026?

    CONTINUUM — the announced collective adjustment for October 2026, relative to September 2026
    required production levels. The scale is anchored to the plausible range for this decision, so
    the status-quo rollover sits at 20, not the midpoint (question-design rule D28.0).

      0 = a collective cut of 150,000 barrels per day or more
     20 = no change; September levels rolled over unchanged (a pause)
    100 = a collective increase of 600,000 barrels per day or more

    Intermediate markers (the scale is linear between the anchors):
     10 = a collective cut of about 75,000 b/d
     40 = a collective increase of about 150,000 b/d
     45 = a collective increase of about 188,000 b/d, matching the June–September 2026 cadence
     47 = a collective increase of about 206,000 b/d, matching the April–May 2026 pace
     60 = a collective increase of about 300,000 b/d
     80 = a collective increase of about 450,000 b/d

    NOTES FOR THE FORMALIZER

    - Establish from current sources which countries are in the voluntary-adjustment group as of
      6 September 2026, and model them as the actors. The UAE left OPEC+ effective 1 May 2026;
      treat non-participants as actors only where sources show them exerting influence on this
      decision.
    - Positions should reflect each producer's revenue needs, spare and actual capacity, standing
      compensation obligations for past overproduction, and any reported stance on the pace of
      unwinding. Where a country's position is not directly sourced, record that in the
      assumptions list rather than asserting a coordinate.
    - Capability in this forum is not equal and not one-country-one-vote: it reflects production
      weight, spare capacity, and the demonstrated ability to move or block a group decision.
      State the capability rule chosen and its basis in the assumptions.
    - Salience should reflect how much the October number matters to each actor — fiscal breakeven
      pressure, and the fact that production during the capacity-assessment window bears on 2027
      baselines.
    - Model external pressure — consuming-state pressure on prices, market conditions, inventory
      levels — as an actor only if sources show it operating on this decision; otherwise place it
      in the assumptions.
    - Horizon: a single scheduled monthly decision, taken with the 2027 baseline negotiation in
      view and against a run of +188 kb/d monthly increases.
    - Every position, salience and capability value must carry an evidence note or appear in the
      assumptions list.
    - The reference class (docs/questions/opec-reference-class.md) is INCOMPLETE and unratified; do
      NOT treat it as evidence unless and until it is ratified.

## Commands

    mkdir -p analyses/opec-oct
    # paste the situation block into analyses/opec-oct/situation.txt, then:
    schelling formalize analyses/opec-oct/situation.txt --search --max-searches 6 -o analyses/opec-oct/opec-oct.json
    schelling report analyses/opec-oct/opec-oct.json --open
    # review the draft, edit what you disagree with. DO NOT solve or seal this session (Session 57
    # stops at the reviewed draft); the grading file GRADING-Q-2026-OPEC-OCT.md is already committed.

## Draft grading rubric — GRADING-Q-2026-OPEC-OCT.md

Committed at repo root before any forecast is sealed; `schelling seal` refuses a forecast whose
question has no rubric. The rubric's canonical continuum text governs; the anchors above summarise
it. Mapping rule: `grade = 20 + (adjustment_kbd / 750) × 100`, clamped to [0, 100], rounded to two
decimal places. A cut is negative, an increase positive, a rollover is exactly 20.
