# Question package — Q-2026-OPEC-SEP

A fast-resolving ledger question. Drafted 2026-07-24, before any forecast is run.
**Resolution 2026-08-05 23:59 UTC · Grading 2026-08-06.** Nine days from drafting.

## Why this question

- **It resolves in nine days.** The seven OPEC+ countries running the additional voluntary
  adjustments meet virtually on 2 August 2026 to set September production levels. Their statement
  and its required-production table publish the same day.
- **The continuum is a real number line.** The outcome is a collective adjustment in barrels per
  day, so grading is arithmetic — no interpretation, no bands to argue over, no room for a
  motivated grader. This is the tightest rubric the ledger will ever carry.
- **Ideal points genuinely differ.** Unlike a "will the talks collapse" question where every actor
  wants the same thing, each producer wants a different number, for documented fiscal and capacity
  reasons. That is what a bargaining model needs to have anything to say.
- **Validated domain.** Consensual multilateral bargaining — the DEU family, where the compromise
  model is proven to the extractable-signal ceiling. US-Iran is coercive and unvalidated; sealing
  both means the ledger tests the machine where its evidence is strongest and where it has none.
- **An external benchmark exists.** Energy desks publish expectations before each meeting, so after
  grading you can compare the machine not only against reality but against professional analysts —
  something neither of the September questions offers.

## Context established from sources, 2026-07-24

The UAE withdrew from OPEC and OPEC+ effective 1 May 2026, leaving seven countries in the
voluntary-adjustment group: Saudi Arabia, Russia, Iraq, Kuwait, Kazakhstan, Algeria and Oman. At
their 5 July 2026 virtual meeting the seven agreed a collective production adjustment of 188,000
b/d for August — reported as the fifth consecutive monthly increase in the gradual unwinding of the
2023 voluntary cuts. August required production levels were published as Saudi Arabia 10.416,
Russia 9.887, Iraq 4.405, Kuwait 2.660, Kazakhstan 1.618, Algeria 1.001 and Oman 0.836 million b/d.
The group also reaffirmed that increases may be paused or reversed as conditions change, and that
the measure gives members an opportunity to accelerate compensation for overproduction since
January 2024. Separately, OPEC+ has approved a mechanism to assess maximum sustainable capacity as
the basis for 2027 baselines — which gives members a live incentive to demonstrate capacity during
the assessment window.

Note for the drafter: at least one low-quality outlet reported the July decision as a *cut* of
188,000 b/d. The primary OPEC statement and the wire services of record report an increase. Prefer
the OPEC secretariat's own statement over aggregators.

## situation.txt (paste-ready)

    QUESTION Q-2026-OPEC-SEP

    What collective crude production adjustment will the OPEC+ countries participating in the
    additional voluntary adjustments announce for September 2026, at their meeting scheduled for
    2 August 2026?

    CONTINUUM — the announced collective adjustment for September 2026, relative to August 2026
    required production levels

      0 = a collective cut of 600,000 barrels per day or more
     50 = no change; August levels rolled over unchanged
    100 = a collective increase of 600,000 barrels per day or more

    Intermediate markers (the scale is linear between the anchors):
     25 = a collective cut of about 300,000 b/d
     42 = a collective cut of about 100,000 b/d
     58 = a collective increase of about 100,000 b/d
     66 = a collective increase of about 190,000 b/d, matching the pace set for August
     75 = a collective increase of about 300,000 b/d
     92 = a collective increase of about 500,000 b/d

    NOTES FOR THE FORMALIZER

    - Establish from current sources which countries are in the voluntary-adjustment group as of
      the meeting date, and model them as the actors. The UAE's withdrawal from OPEC+ in May 2026
      is material context; treat non-participants as actors only where sources show them exerting
      influence on this decision.
    - Positions should reflect each producer's revenue needs, spare and actual capacity, standing
      compensation obligations for past overproduction, and any reported stance on the pace of
      unwinding. Where a country's position is not directly sourced, record that in the
      assumptions list rather than asserting a coordinate.
    - Capability in this forum is not equal and not one-country-one-vote: it reflects production
      weight, spare capacity, and the demonstrated ability to move or block a group decision.
      State the capability rule chosen and its basis in the assumptions.
    - Salience should reflect how much the September number matters to each actor — fiscal
      breakeven pressure, and the fact that production during the capacity-assessment window bears
      on 2027 baselines.
    - Model external pressure — consuming-state pressure on prices, market conditions, inventory
      levels — as an actor only if sources show it operating on this decision; otherwise place it
      in the assumptions.
    - Horizon: a single scheduled monthly decision, taken with the 2027 baseline negotiation in
      view.
    - Every position, salience and capability value must carry an evidence note or appear in the
      assumptions list.

## Commands

    mkdir -p analyses/opec
    # paste the situation block into analyses/opec/situation.txt, then:
    schelling formalize analyses/opec/situation.txt --search --max-searches 6 -o analyses/opec/opec.json
    schelling report analyses/opec/opec.json --open
    # review the draft, edit what you disagree with, commit the grading file, then:
    schelling solve analyses/opec/opec.json --draws 10000 --seed 42
    schelling llm-forecast analyses/opec/opec.json
    schelling seal "runs/$(ls -t runs | head -1)" --vintage v1

Seal all three records — challenge, compromise, and the LLM baseline — so this question carries the
full three-way comparison.

## Draft grading rubric — GRADING-Q-2026-OPEC-SEP.md

Commit this before sealing; `schelling seal` refuses a forecast whose question has no rubric.

**Binary criterion.** The question resolves on the collective production adjustment for September
2026 announced by the participating countries on or before 2026-08-05 23:59 UTC, as stated in the
OPEC Secretariat's published statement. If no adjustment is announced by that time, August levels
stand and the outcome is a rollover. If the statement announces a schedule rather than a single
figure, the September component governs. The headline collective adjustment figure governs, not
any compensation-adjusted figure quoted separately by third parties.

**Adjudicating sources (precedence order).** 1. The OPEC Secretariat's published statement and the
required-production table issued with it. 2. OPEC's Monthly Oil Market Report. 3. Wire services of
record (Reuters, Associated Press, Bloomberg) corroborating 1-2. Where sources genuinely conflict,
grade at the midpoint of the defensible range and record the disagreement.

**Mapping rule.** The announced collective adjustment in thousands of b/d maps linearly onto the
continuum:

    grade = 50 + (adjustment_kbd / 600) x 50

clamped to [0, 100] and rounded to the nearest integer. A cut is negative, an increase positive, a
rollover is exactly 50. The arithmetic governs; no discretionary band applies. The grader publishes
the announced figure, the computed grade, and the citation.

**Canonical text.** The sealed game's continuum text governs; the anchors above summarise it.

**Grading formula.** score(r) = |r.ensemble.median - actual| per sealed record on the 0-100
continuum. All sealed records are scored — challenge, compromise, and llm-judgment — and the grade,
its justification, and all cited sources are published in FORECASTS.md at grading.

**Integrity checks before scoring.** `schelling verify` on every sealed record; the ledger's
OpenTimestamps proof checked with `ots verify` to confirm the commitment predates resolution.

**Final:** no edits to this rubric under any circumstances after 2026-08-05.
