# The precedent layer — the outside view

`schelling precedents <game-or-draft.json> [--search]` builds a reference class of prior comparable
decisions, each placed on the current question's 0–100 continuum, for comparison against the
structural model. Every placement is a **proposal** until a human ratifies it (`ratified: true` + a
quoted `ratification_note`); only then does it feed the reference-class panel or the evidence river.
See `src/schelling/precedents/` and D29.

## Standing rule: the population first, then the outcomes (D30.1)

**The reference class is SESSIONS-AT-RISK, not notable outcomes.** Identify the full *population of
decision opportunities* first — every occasion on which the decision could have been taken — and only
then record what each one decided. **Sessions that decided nothing are part of the class**: a body
that met and adopted no resolution is a data point that places in the no-action band, not an absence.

Listing only the dramatic outcomes (the censures, the referrals) and computing a rate over them is
**selection bias**: it silently drops the quiet sessions and overstates the probability of action. The
lesson is general — a base rate is only meaningful over a denominator of opportunities, so enumerate
the denominator before you count the numerator.

For **Q-2026-IAEA-SEP** the class is *every IAEA Board of Governors session (regular or special) at
which Iran was on the agenda, from a stated start date* — each placed on the continuum, including the
sessions that adopted nothing (which place in the no-action band 40–59).

## INCOMPLETE beats a biased base rate

The population size (`sessions_at_risk`, the denominator) must come from the records. **If the full
enumeration cannot be sourced, the reference class is reported as INCOMPLETE — the fraction covered is
stated and NO base rate is computed.** A distribution over a partial, outcome-selected sample would
overstate action; an honest "N of M sessions covered" does not. A base rate (and therefore the
outside-view divergence diagnostic) appears only when the class is complete: the ratified
ex-ante-codable precedents span the full `sessions_at_risk` population.

## GDELT candidates and the auto-coding caveat (Session 46, D46.2)

`schelling gdelt` queries the GDELT global news database for candidate comparable events — an actor
pair, an institution, or an event type over a date range — and writes them as an **unratified
precedents draft**, exactly like the LLM finder's output. GDELT feeds the **precedent layer only**;
it is never a source for the evidence river, and nothing it returns is trusted automatically.

GDELT's coding is machine-generated from the worldwide news stream at scale, so its candidates carry
the standard auto-coding hazards, and a human must account for each before ratifying:

- **Duplicate reports.** One real event is reported by many outlets and can appear as many candidate
  rows. Deduplication by URL removes exact repeats, but syndicated and rewritten copies of the same
  event survive; the analyst must collapse them to one precedent.
- **Circular reporting.** Outlets cite each other, so a single unverified claim can look like broad
  corroboration. Volume in GDELT is not independent confirmation.
- **Erroneous codings.** The event/CAMEO classification is automated and sometimes simply wrong — a
  metaphor read as an event, the wrong actors, a mis-parsed date. The CAMEO code recorded on a
  candidate is the code the *query* targeted, not an adjudicated coding of the article.

For these reasons every GDELT candidate lands with `ratified: false`, a **PLACEMENT PENDING**
placeholder, and no `ratification_note`. The reference-class panel ignores it until a human sets its
real placement on the continuum, marks it ratified, and quotes a ratification — the same gate the
LLM-proposed precedents pass. The panel also surfaces this caveat inline whenever precedents are
shown, so a reader of the report knows machine-sourced candidates were filtered by hand, not trusted.
