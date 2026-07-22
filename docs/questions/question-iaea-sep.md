# Question package — Q-2026-IAEA-SEP

Second sealed-ledger question: same conflict, different game. Drafted 2026-07-22, before any
forecast is run.

## Why this is genuinely different from Q-2026-USIRAN-STAGE2

The sealed question forecasts a **bilateral coercive bargain** — where the US-Iran settlement lands.
This one forecasts a **multilateral committee vote**: what the IAEA Board of Governors, 35 member
states, decides to do about Iran at its September 2026 meeting.

- **Different actors.** Not Washington and Tehran, but the Board — the US, the E3, Russia, China,
  and the Non-Aligned bloc that holds the swing seats. Iran is not even a voting member of the
  game it is the subject of.
- **Different mechanism.** Committee bargaining under a voting rule, not coercive exchange under
  the shadow of force.
- **Different domain, and this is the point.** Committee voting is the DEU family — the one domain
  where the compromise model is validated to the extractable-signal ceiling. The sealed question is
  coercive and unvalidated. Sealing both tests the machine where its evidence is strongest and where
  it has none, on the same underlying conflict.
- **Honest caveat about correlation.** Two questions on one conflict share a common failure mode: if
  the machine misreads the conflict's fundamentals, both go wrong together. That is a real cost, and
  also a real research design — same conflict, two mechanisms, so a divergence between them is
  diagnostic rather than noise. Stated here so it is on the record before the forecast exists.

**Resolution 2026-09-30 23:59 UTC · Grading 2026-10-05.** (The September Board ordinarily convenes
in the first half of September; the window is set to month-end so a schedule shift cannot break the
question, and it captures any special session in the same month.)

## Live context established from sources, 2026-07-22

Following the June 2025 attacks on Iranian nuclear installations, IAEA inspection work was suspended
completely — the first such break since Iran's comprehensive safeguards agreement was adopted — and
Iran's parliament passed a law suspending cooperation with the Agency. By the February 2026 Board
report, Iran had given access at least once to each of its *unaffected* facilities, but had provided
no declarations, reports, or access for any facility that had been attacked, leaving the Agency
unable to fulfil its safeguards obligations for those sites. A special session of the Board met on
2 March 2026. On 10 June 2026 the Board adopted a resolution urging Iran to cooperate, following the
Director General's report of 4 June. The file is live, contested, and on a quarterly cycle.

## situation.txt (paste-ready)

    QUESTION Q-2026-IAEA-SEP

    What action will the IAEA Board of Governors take on Iran at its September 2026 meeting?

    CONTINUUM — the severity of Board action, from maximal pressure on Iran to maximal accommodation

      0 = the Board adopts a resolution finding Iran in non-compliance with its safeguards
          obligations and reporting or referring the matter to the UN Security Council
     50 = no new resolution is adopted; the Director General's report is noted and the matter is
          left to the diplomatic track
    100 = the Board closes or normalises the Iran file, ending Iran-specific reporting requirements

    Intermediate markers:
     15 = a censure resolution demanding immediate access, with explicit escalation language but no
          referral
     30 = a resolution urging cooperation, in terms similar to or modestly firmer than the
          resolution adopted on 10 June 2026
     65 = the Board welcomes or endorses an agreed modalities arrangement between Iran and the
          Agency restoring inspection access
     85 = the Board welcomes substantially restored safeguards implementation, including at
          facilities affected by military attack

    NOTES FOR THE FORMALIZER

    - The actors are Board members and blocs, not the parties to the bilateral talks. Establish the
      current composition of the 35-member Board from sources; aggregate members into blocs where
      the sources treat them jointly, and disclose every aggregation as an assumption.
    - Model the Director General and the Secretariat as an actor only if the sources show the
      Agency's own position shaping the outcome; otherwise note it in the assumptions.
    - Iran is the subject of the decision, not a voting member. Include it as an actor only to the
      extent sources show it exerting influence on Board members, and say so explicitly.
    - Capability here reflects Board voting weight under the Board's own rules together with
      diplomatic weight and the demonstrated ability to assemble or block a majority. State the
      capability rule chosen and its basis.
    - Salience should reflect how much the September outcome matters to each member — for some
      states this file is existential diplomacy, for others a routine agenda item.
    - The state of the parallel US-Iran diplomatic track as of the meeting is context that moves
      positions; cite it where it is used, and do not import any conclusion from another analysis.
    - Horizon: a single scheduled quarterly decision, taken with the November Board in view.
    - Every position, salience and capability value must carry an evidence note or appear in the
      assumptions list.

## Commands

    schelling formalize analyses/iaea/situation.txt --search --max-searches 6 -o analyses/iaea/iaea.json
    schelling report analyses/iaea/iaea.json --open
    # review the draft, edit what you disagree with, commit the grading file, then:
    schelling solve analyses/iaea/iaea.json --draws 10000 --seed 42
    schelling seal "runs/$(ls -t runs | head -1)" --vintage v1

## Draft grading rubric — GRADING-Q-2026-IAEA-SEP.md

Ratify or amend this the way the US-Iran rubric was ratified; it must be committed before sealing.

**Binary criterion.** The question resolves on the formal output of the IAEA Board of Governors
concerning Iran adopted on or before 2026-09-30 23:59 UTC, at its September regular session or any
special session held within the window. Statements by individual member states, Director General
reports, and chair's remarks are not Board action; only adopted resolutions or formal decisions
count as such. If no resolution or decision is adopted, the outcome grades in the no-action band.

**Adjudicating sources (precedence order).** 1. The text of any resolution or decision adopted by
the Board, as published by the IAEA. 2. IAEA Board reports and the Director General's introductory
statement. 3. IAEA press releases and the Agency's chronology of key events. 4. Wire services of
record (Reuters, Associated Press) corroborating 1-3. Where sources genuinely conflict, grade at the
midpoint of the defensible range and record the disagreement.

**Mapping bands (tile 0-100, no gaps or overlaps).**

| Board outcome by 2026-09-30 | Band |
|---|---:|
| Non-compliance finding and/or referral or report to the UN Security Council | 0-9 |
| Censure resolution demanding immediate access, explicit escalation language, no referral | 10-24 |
| Resolution urging cooperation, comparable to or modestly firmer than 10 June 2026 | 25-39 |
| No new resolution or decision; report noted; matter left to the diplomatic track | 40-59 |
| Board welcomes or endorses an agreed modalities arrangement restoring inspection access | 60-74 |
| Board welcomes substantially restored safeguards implementation including attacked facilities | 75-89 |
| Board closes or normalises the Iran file, ending Iran-specific reporting | 90-100 |

**Canonical text.** The sealed game's continuum text governs; the anchors above summarise it.

**Midpoint default.** Within a band the grade defaults to the band midpoint; any deviation must cite
specific adopted language in the justification paragraph.

**Grading formula.** score(r) = |r.ensemble.median - actual| per sealed record on the 0-100
continuum. All sealed records are scored; the grade integer, its justification, and all cited
sources are published in FORECASTS.md at grading.

**Integrity checks before scoring.** `schelling verify` on every sealed record; the ledger's
OpenTimestamps proof checked with `ots verify` to confirm the commitment predates resolution.

**Final:** no edits to this rubric under any circumstances after 2026-09-30.
