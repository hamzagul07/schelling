# SPEC — Model Three (working name: Asabiyyah)
**Version MT-1.0 · Pre-registered specification · Frozen upon commit, before the coercive library exists**

Status: this specification is committed while the case library holds two verified cases, none
coercive. Every parameter below is fixed now; none may ever be fitted, tuned, or revised. Any change
produces MT-1.1, a different model whose results are reported separately and never substituted for
MT-1.0's. The model is scored once, at the library's pre-registered 8-verified-case reading,
alongside the challenge model, the compromise mean, and each source study's own published forecast.

## 1. Claim

For coercive and asymmetric standoffs, settlement outcomes deviate from the capability-and-salience
weighted mean in four theoretically predicted ways: internal cohesion multiplies effective power
(Ibn Khaldun; military-effectiveness literature); comfort erodes the willingness to endure over
time while hardened and sacred-stakes actors do not decay (Ibn Khaldun; Mueller; Toft/Hassner);
settlements requiring the weaker side to accept vulnerability gravitate toward the status quo when
no credible guarantor exists (Walter); and mutually active misperception — the stronger side's
grievance-ledger, the weaker side's fear-lens — pulls outcomes toward the status quo by suppressing
the concessions both sides could afford (the Grape Trap). Loss-framed actors additionally bargain
with intensified weight (prospect theory). MT-1.0 operationalizes exactly these five terms on top of
the compromise mean, and nothing else.

## 2. Inputs

Per actor, from the case table: position p_i, salience s_i, capability c_i (source's own scales,
normalized 0–100). Per actor, coded ex ante under §5: cohesion class h_i ∈ {fractured, baseline,
exceptional}; endurance class e_i ∈ {hardened, comfortable}; loss-domain flag L_i ∈ {0,1};
perception mode m_i ∈ {ledger, lens, none}. Per case: reference point rp (status quo on the
continuum) where the source provides or the coders can anchor one; horizon T in months (the source's
stated horizon, per the library's horizon rule); vulnerability flag V ∈ {0,1} — does the contested
settlement require the materially weaker side to accept post-deal vulnerability (disarmament,
capability surrender, exposure); guarantor flag G ∈ {0,1} — is at least one third party with both
capability and stake credibly committed to enforcement.

## 3. The model

Applied in this order; all multiplications capped so no salience exceeds 100.

1. **Loss intensity.** s_i ← min(100, s_i × 1.15) for each actor with L_i = 1.
2. **Comfort decay.** If T ≥ 18 months: s_i ← s_i × 0.80 for each actor with e_i = comfortable.
   Hardened actors never decay. (Indivisibility/sacred framing per canon D2 automatically grants
   hardened class in coding — sacred stakes do not tire.)
3. **Cohesion multiplier.** c_i ← c_i × h_i with h = 0.85 (fractured), 1.00 (baseline),
   1.15 (exceptional).
4. **Adjusted mean.** WM′ = Σ p_i·c_i·s_i / Σ c_i·s_i over the adjusted values.
5. **Status-quo pull.** λ = min(0.40, 0.25·[V=1 and G=0] + 0.15·[trap active]), where the trap is
   active iff the case's materially stronger principal codes m=ledger AND the weaker principal
   codes m=lens. Prediction = (1−λ)·WM′ + λ·rp. If the case has no codable rp, λ-terms are
   inactive and the prediction is WM′ (recorded as such).

**Fixed constants and their honest status.** 1.15 (loss), 0.80 (decay), 0.85/1.15 (cohesion), 0.25
(guarantee pull), 0.15 (trap pull), 18 months, 0.40 (pull cap). None is derived from an estimate;
each is a conventional magnitude fixed in advance. A sensitivity grid is pre-registered as a
SECONDARY, descriptive analysis only: loss {1.10, 1.15, 1.20}; decay {0.70, 0.80, 0.90}; guarantee
pull {0.15, 0.25, 0.35}; trap pull {0.10, 0.15, 0.20}. The primary gate uses the primary constants
only. The grid may never be used to select a better-performing variant post hoc.

## 4. Predictions this model stakes (the hypothesis registry)

H1: MT-1.0 achieves lower MAE than the unadjusted compromise mean on the coercive library.
H2: The largest single-term contribution comes from the guarantee pull (Walter's term).
H3: Cases with an active trap and no guarantor land in the status-quo band more often than the
mean predicts.
H4: Comfortable-side forecasts that ignore decay overstate that side's achieved outcome at long
horizons.
Each hypothesis is graded directionally at the reading; at N=8 no significance is claimed —
direction and paired-bootstrap intervals are reported, and the claim level scales only as N grows.

## 5. Coding protocol for the new inputs

All flags are coded ex ante — from sources predating the case's outcome wherever the case is
historical — with a citation per flag, entered under the library's blind dual-entry protocol, and
ratified with the case's verification. Flags are sealed with the case, before any model runs.
Rules: h from canon B3 observables (elite fragmentation, defection/desertion indicators,
politicization, mobilization capacity — exceptional requires positive evidence, fractured requires
positive evidence, silence codes baseline); e from comfort proxies (wealth, casualty insulation,
accountability breadth) with sacred-stakes framing (canon D2 rule) forcing hardened; L from the
actor's own framing of the status quo as intolerable loss (canon A3 rule); m from the Grape Trap
rule — itemized-grievance hostility codes ledger, generalized-filter hostility codes lens, and only
principals are coded; V and G from the settlement terms under negotiation and the documented
commitments of third parties (canon D1 rule). A coding sheet template accompanies the library
schema; ambiguous flags default to the null value (baseline / hardened-only-if-evidenced / 0 /
none) and the ambiguity is recorded.

## 6. Gates (immovable)

Primary: at the pre-registered 8-verified-case coercive reading, MT-1.0 must beat the unadjusted
compromise mean on MAE, reported with paired bootstrap intervals. Secondary: comparison against the
challenge model and against each source's own published forecast; per-term descriptive ablation;
the sensitivity grid. Negative results are published with the same prominence as positive ones. If
MT-1.0 fails, it is retired exactly as R1's candidates were; its committed specification remains as
the record that the theory stated its claim before the evidence existed.

## 7. Provenance

Base: the capability×salience compromise mean (Black's spatial tradition; the survivor of this
project's Sessions 9–R1 and the DEU ceiling result). Terms: Ibn Khaldun (Muqaddimah, 1377) via
canon E1/B3; Walter (1997, 2002) via D1; Toft (2003)/Hassner (2003) via D2 as hardening; Kahneman &
Tversky (1979)/Levy (1997) via A3; the Grape Trap (house theory, under peer review) via E2, its
parameters fixed here by convention, never fitted. Selection and exclusion log: canon A1 excluded
as redundant with salience; B1 excluded to avoid re-adjusting expert-coded capabilities; A5 and C5
excluded on CONTESTED evidence tags; B5 excluded as represented by the actor table itself; D5
noted for possible MT-1.1 consideration, excluded from MT-1.0 for term-count discipline.
