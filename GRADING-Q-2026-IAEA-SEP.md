# GRADING — Q-2026-IAEA-SEP

**Pre-registered 2026-07-22, before resolution (2026-09-30), awaiting Hassan's ratification of any
amendments; final after 2026-09-30.** Fixed in advance so the score cannot be reverse-fit to the
outcome. Referenced from [FORECASTS.md](FORECASTS.md); its rationale is on the record in
[docs/questions/question-iaea-sep.md](docs/questions/question-iaea-sep.md).

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

## Machine-readable rubric (canonical, embedded)

The exact `ResolutionRubric` object (schema: `schemas/question.py` → `ResolutionRubric`) — the
machine-readable form of everything above, added 2026-07-22 (pre-resolution, D24.2) so
`schelling report` can resolve it and render the two-audience report.

> **Provenance of the `bands` array — 2026-07-22 (D24.4):** Bands array added 2026-07-22 as a
> structured restatement of the seven bands already committed in outcome_mapping — identical
> boundaries and meaning, no semantic change, added so the report renders the probability strip. The
> prose outcome_mapping and the sealed continuum text remain canonical; if the array and the prose
> ever disagree, the prose governs. Pre-resolution; rubric is excluded from inputs_hash so no sealed
> record, ledger entry, or timestamp is affected.

```json
{
  "resolution_criteria": "The question resolves on the formal output of the IAEA Board of Governors concerning Iran adopted on or before 2026-09-30 23:59 UTC, at its September regular session or any special session held within the window. Statements by individual member states, Director General reports, and chair's remarks are not Board action; only adopted resolutions or formal decisions count. If no resolution or decision is adopted, the outcome grades in the no-action band.",
  "adjudicating_sources": [
    "The text of any resolution or decision adopted by the Board, as published by the IAEA",
    "IAEA Board reports and the Director General's introductory statement",
    "IAEA press releases and the Agency's chronology of key events",
    "Wire services of record (Reuters, Associated Press) corroborating the above"
  ],
  "outcome_mapping": "Place the Board's adopted action in exactly one band (the bands tile 0-100 with no gaps or overlaps): non-compliance finding and/or referral or report to the UN Security Council 0-9; censure resolution demanding immediate access, explicit escalation language, no referral 10-24; resolution urging cooperation, comparable to or modestly firmer than 10 June 2026 25-39; no new resolution or decision, report noted, matter left to the diplomatic track 40-59; Board welcomes or endorses an agreed modalities arrangement restoring inspection access 60-74; Board welcomes substantially restored safeguards implementation including attacked facilities 75-89; Board closes or normalises the Iran file, ending Iran-specific reporting 90-100. Within a band the grade defaults to the band midpoint; any deviation must cite specific adopted language. The sealed game's continuum text is canonical; these anchors summarise it.",
  "grading_formula": "score(r) = |r.ensemble.median - actual| per sealed record on the 0-100 continuum; the grade integer, its justification, and all cited sources are published in FORECASTS.md at grading.",
  "bands": [
    {"lo": 0, "hi": 9, "label": "Non-compliance finding and/or referral to the UN Security Council"},
    {"lo": 10, "hi": 24, "label": "Censure resolution demanding immediate access, no referral"},
    {"lo": 25, "hi": 39, "label": "Resolution urging cooperation, comparable to 10 June 2026"},
    {"lo": 40, "hi": 59, "label": "No new resolution; report noted; left to the diplomatic track"},
    {"lo": 60, "hi": 74, "label": "Board welcomes an agreed modalities arrangement restoring access"},
    {"lo": 75, "hi": 89, "label": "Board welcomes substantially restored safeguards implementation"},
    {"lo": 90, "hi": 100, "label": "Board closes or normalises the Iran file"}
  ]
}
```
