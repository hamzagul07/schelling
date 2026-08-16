# Question packages — and the OPEC monthly-decision series

Each sealed ledger question is drafted as a **question package** before any forecast runs. A package
is a small, fixed set of files:

| File | What it is |
|---|---|
| `docs/questions/question-<id>.md` | the rationale, the sourced context, the paste-ready `situation.txt`, and the workflow commands |
| `GRADING-Q-<id>.md` (repo root) | the pre-registered grading rubric — binary criterion, adjudicating sources, mapping rule, and the machine-readable `outcome_map` |
| a formalized draft under `analyses/<id>/` (gitignored) | the `formalize --search` output, reviewed before solving/sealing |

The IAEA and both OPEC questions are worked examples: `question-iaea-sep.md`,
`question-opec-sep.md`, `question-opec-oct.md`.

---

## The OPEC monthly-decision series (Session 57 scaffolding, D57.4)

The OPEC+ additional-voluntary-adjustment group decides a collective production adjustment every
month. That makes a **series** of near-identical questions — `Q-2026-OPEC-SEP`, `Q-2026-OPEC-OCT`,
and each month after. The point of the scaffolding is that a new month is a **date-and-anchor edit,
not a rewrite**. Two artifacts are factored to the *series* level and are reused unchanged month to
month:

- **`docs/questions/opec-reference-class.md`** — the pre-registered sessions-at-risk denominator
  (D30.1/D30.2). Its definition is fixed; only the coverage/verdict is re-checked as new months
  resolve.
- **`docs/questions/opec-oct-coordinates.md`** — the actor-coordinate sourcing method (IMF breakeven
  → salience, OPEC required table → capability, positions inferred). The *method* is reused; only the
  refreshed figures change.

### What varies each month (the only edits)

1. **Identifiers & dates** — question id `Q-2026-OPEC-<MON>`, the production month, the meeting date,
   the resolution date, the grading date.
2. **Continuum anchors** — reuse `0 = a 150 kb/d cut, 20 = rollover, 100 = a 600 kb/d increase`
   **while the regime is stable**. Re-anchor only if the plausible range genuinely shifts, and if you
   do, apply D28.0 (status quo off the midpoint) and the anchor-to-plausible-range rule again.
3. **The "recent cadence" markers** — the one or two intermediate markers that name the current
   monthly pace (e.g. `45 = +188 kb/d`), refreshed from the last decisions.
4. **The context paragraph** — the last few decisions and the participant list, refreshed from
   `opec-reference-class.md`.

### What stays fixed

The package structure; the mapping-rule *form* (`grade = intercept + (adj_kbd / span) × 100`, two
decimals, D57.1); the adjudicating-source precedence; the grading formula; the reference-class
definition; the coordinate-sourcing method; the discipline notes (D28.0, D57.1, "prose governs").

### Per-month checklist

1. Copy `_template-opec-monthly.md` → `question-opec-<mon>.md`; fill the `<<…>>` fields.
2. Copy `GRADING-Q-2026-OPEC-SEP.md` (or OCT) → `GRADING-Q-2026-OPEC-<MON>.md`; edit dates, the
   production month, and — only if re-anchored — the `outcome_map` (`slope`, `intercept`, `rounding`)
   and its prose. Add a matching drift-guard test in `tests/test_grading_machinery.py`.
3. Re-check the reference class: has coverage changed? Is it now COMPLETE? Ratify or leave INCOMPLETE.
4. Refresh coordinates (`schelling evidence dbnomics …`) and update the sourcing audit.
5. `schelling formalize analyses/opec-<mon>/situation.txt --search --max-searches 6 -o …`; review.
6. Solve / seal only when the milestone calls for it; grade after resolution.

A stable series should touch only steps 1–2's dated fields and step 3–4's refreshed figures.
