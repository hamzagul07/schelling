# Actor coordinates — Q-2026-OPEC-OCT (sourcing audit)

The v2-vintage acceptance test (D37.2/D37.3), applied to `Q-2026-OPEC-OCT`: for each actor, what
fraction of its coordinate *basis* is now grounded in a sourced figure versus left to inference. No
dressing up. Coordinates themselves (position/salience/capability on 0–100) are assigned by the
formalizer, never by DBnomics — DBnomics supplies the citable figure that *grounds* a coordinate; the
firewall keeps it from writing one (CLAUDE.md §1/§6). Sourced 2026-08-16.

The seven actors (the AVA group after the UAE's 1 May 2026 exit): Saudi Arabia, Russia, Iraq, Kuwait,
Kazakhstan, Algeria, Oman.

## The three coordinate bases and their sourcing

### 1. Fiscal breakeven → grounds SALIENCE (how much the number matters fiscally)

Sourced from **IMF Regional Economic Outlook (MCDREO), series `PZPIOILBE_G_USD`** — breakeven fiscal
oil price, US$/bbl, 2025 — via `schelling evidence dbnomics --series IMF/MCDREO/A.<ISO>.PZPIOILBE_G_USD`
(retrieved 2026-08-16, db.nomics.world):

| Actor | Breakeven fiscal oil price (US$/bbl, 2025) | Status |
|---|---:|---|
| Saudi Arabia | 90.94 | **sourced** (IMF/MCDREO/A.SA) |
| Iraq | 92.43 | **sourced** (IMF/MCDREO/A.IQ) |
| Kuwait | 81.84 | **sourced** (IMF/MCDREO/A.KW) |
| Kazakhstan | 115.93 | **sourced** (IMF/MCDREO/A.KZ) |
| Algeria | 118.95 | **sourced** (IMF/MCDREO/A.DZ) |
| Oman | 57.31 | **sourced** (IMF/MCDREO/A.OM) |
| Russia | — | **inferred** — Russia is outside the Middle East & Central Asia REO, so MCDREO carries no series for it; its breakeven must come from another source or be inferred, and is recorded as an assumption, not asserted here. |

Six of seven breakevens are sourced. Reading (for the formalizer, not a coordinate): Algeria,
Kazakhstan, Iraq and Saudi Arabia run high breakevens (≈$90–120) — more fiscal pressure to favour
higher prices / a slower unwind — while Oman is comparatively low; Russia is unsourced here.

### 2. Production required level → grounds CAPABILITY (weight in the forum)

Sourced from the **OPEC Secretariat required-production table** issued with each monthly statement
(authoritative, per-actor, all seven). The August 2026 required levels published with the group's
statements — Saudi Arabia 10.416, Russia 9.887, Iraq 4.405, Kuwait 2.660, Kazakhstan 1.618, Algeria
1.001, Oman 0.836 million b/d — establish the production weights; the September/October levels come
from the same table as the unwind proceeds. **Capability basis: sourced for all 7.** (DBnomics EIA/JODI
actual-production series can corroborate but the OPEC required table is the figure of record.)

### 3. Inventories → market-level SALIENCE context, not an actor coordinate

Commercial stock levels (OECD / US EIA) are a *market* variable that moves the whole group's
incentive, not a per-actor coordinate. It is sourced at the market level (EIA/IEA) and enters as
shared context / an assumption; **per-actor, inventories are inferred** (they do not vary the actors
against each other).

## Per-actor sourced-vs-inferred ledger

Coordinate bases counted per actor: breakeven (salience), production weight (capability), position
(ideal point). Positions are **inferred for all seven** — no participant publishes its preferred
October figure, exactly as the SEP v2 vintage recorded ("no actor's position is delegate-sourced").

| Actor | Breakeven | Production weight | Position | Sourced / total |
|---|---|---|---|---:|
| Saudi Arabia | sourced | sourced | inferred | 2 / 3 |
| Iraq | sourced | sourced | inferred | 2 / 3 |
| Kuwait | sourced | sourced | inferred | 2 / 3 |
| Kazakhstan | sourced | sourced | inferred | 2 / 3 |
| Algeria | sourced | sourced | inferred | 2 / 3 |
| Oman | sourced | sourced | inferred | 2 / 3 |
| Russia | **inferred** | sourced | inferred | 1 / 3 |

**Summary (honest, no dressing up).** Capability is grounded for all seven (OPEC required-production
table). Salience is grounded for six of seven (IMF breakevens; Russia is the gap). Positions are
inferred for all seven. This is the same shape as the OPEC-SEP v2-sourced vintage: capabilities
well-sourced, salience partly sourced, ideal points inferred. The formalizer must record every
inferred coordinate in the assumptions list rather than asserting it, and `formalize --search` should
try to close the Russia-breakeven and position gaps live.
