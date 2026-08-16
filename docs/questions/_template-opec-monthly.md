# Question package — Q-2026-OPEC-<<MON>>

TEMPLATE for the OPEC monthly-decision series (see `README.md`). Copy this file, replace every
`<<…>>` field, and refresh the context paragraph and cadence markers. Everything not in `<<…>>` is
fixed series text — do not rewrite it. Drafted <<DRAFT-DATE>>, before any forecast is run.
**Resolution <<RES-DATE>> 23:59 UTC · Grading <<GRADE-DATE>>.**

## Why this question

- **It resolves quickly and arithmetically.** The AVA group meets on <<MEETING-DATE>> to set
  <<PROD-MONTH>> production; the outcome is a collective adjustment in barrels per day, graded by a
  linear formula.
- **It applies D28.0.** The continuum anchors to the plausible range so the status-quo rollover sits
  at 20, not the midpoint.
- **Two decimals, not one integer** (D57.1).
- **A reference class exists** (`opec-reference-class.md`) — reuse its verdict; ratify before it feeds.
- **The series is live** — extends the scored OPEC monthly-decision series.

## Context established from sources, <<DRAFT-DATE>>

<<Refresh: the participant list, the last 3–4 monthly decisions and their figures, the current
cadence, any pause, and the capacity-assessment context. Cite via `opec-reference-class.md`.>>

## situation.txt (paste-ready)

    QUESTION Q-2026-OPEC-<<MON>>

    What collective crude production adjustment will the OPEC+ countries participating in the
    additional voluntary adjustments announce for <<PROD-MONTH>>, at their meeting scheduled for
    <<MEETING-DATE>>?

    CONTINUUM — the announced collective adjustment for <<PROD-MONTH>>, relative to <<PREV-MONTH>>
    required production levels. Anchored to the plausible range, so the status-quo rollover sits at
    20, not the midpoint (D28.0).

      0 = a collective cut of 150,000 barrels per day or more
     20 = no change; <<PREV-MONTH>> levels rolled over unchanged (a pause)
    100 = a collective increase of 600,000 barrels per day or more

    Intermediate markers (linear between the anchors):
     10 = a collective cut of about 75,000 b/d
     40 = a collective increase of about 150,000 b/d
     <<CADENCE-MARKER, e.g. 45 = a collective increase of about 188,000 b/d, the recent cadence>>
     60 = a collective increase of about 300,000 b/d
     80 = a collective increase of about 450,000 b/d

    NOTES FOR THE FORMALIZER

    - Establish from current sources which countries are in the group as of <<MEETING-DATE>>, and
      model them as the actors.
    - Positions reflect revenue needs, spare and actual capacity, compensation obligations, and any
      reported stance on the pace of unwinding; unsourced positions go in the assumptions list.
    - Capability reflects production weight, spare capacity, and ability to move or block; state the
      rule and its basis.
    - Salience reflects fiscal breakeven pressure and the 2027-baseline capacity-assessment window.
    - Model external pressure only where sources show it operating on this decision.
    - Horizon: a single scheduled monthly decision.
    - Every position, salience and capability value carries an evidence note or an assumption.
    - The reference class is candidate evidence only until ratified.

## Commands

    mkdir -p analyses/opec-<<mon>>
    schelling formalize analyses/opec-<<mon>>/situation.txt --search --max-searches 6 -o analyses/opec-<<mon>>/opec-<<mon>>.json
    schelling report analyses/opec-<<mon>>/opec-<<mon>>.json --open
    # review; solve/seal only when the milestone calls for it.

## Draft grading rubric — GRADING-Q-2026-OPEC-<<MON>>.md

Committed at repo root before sealing. Mapping rule (reuse unless re-anchored):
`grade = 20 + (adjustment_kbd / 750) × 100`, clamped [0, 100], two decimals. Rollover = 20.
