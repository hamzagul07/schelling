"""Model Three — "Asabiyyah" (MT-1.0), the pre-registered coercive settlement model (Session 20).

A faithful, frozen implementation of ``specs/MT-1.0.md`` section 3: five theory-motivated
adjustments on top of the compromise mean, in the stated order with the salience cap
enforced, the λ composition and cap, and the no-reference-point fallback exactly as written. **Every
constant is fixed by the spec and may never be fitted, tuned, or revised** (any change is MT-1.1, a
different model). The constants block below quotes the spec's literals character-for-character; the
test suite asserts the match against ``specs/MT-1.0.md``.

This module is pure and deterministic: same inputs -> same output. It is scored ONCE, at the
pre-registered 8-verified-case coercive reading — never against the real library before then.
"""

from __future__ import annotations

from dataclasses import dataclass

SPEC = "specs/MT-1.0.md"


@dataclass(frozen=True)
class MTConstants:
    """The frozen MT-1.0 constants (specs/MT-1.0.md §3). None is derived from an estimate."""

    loss_intensity: float = 1.15  # "1.15" (loss)
    comfort_decay: float = 0.80  # "0.80" (decay)
    decay_horizon_months: int = 18  # "18 months"
    cohesion_fractured: float = 0.85  # "0.85" (cohesion, fractured)
    cohesion_baseline: float = 1.00  # "1.00" (cohesion, baseline)
    cohesion_exceptional: float = 1.15  # "1.15" (cohesion, exceptional)
    guarantee_pull: float = 0.25  # "0.25" (guarantee pull)
    trap_pull: float = 0.15  # "0.15" (trap pull)
    lambda_cap: float = 0.40  # "0.40" (pull cap)
    salience_cap: float = 100.0  # "no salience exceeds 100"


MT = MTConstants()

# (spec literal, code value) pairs from §3's constants sentence — verified present in the spec and
# equal to the code by ``test_constants_match_spec_character_for_character``.
SPEC_CONSTANTS: tuple[tuple[str, float], ...] = (
    ("1.15", MT.loss_intensity),
    ("0.80", MT.comfort_decay),
    ("0.85", MT.cohesion_fractured),
    ("1.00", MT.cohesion_baseline),
    ("1.15", MT.cohesion_exceptional),
    ("0.25", MT.guarantee_pull),
    ("0.15", MT.trap_pull),
    ("18 months", float(MT.decay_horizon_months)),
    ("0.40", MT.lambda_cap),
)

_COHESION = {
    "fractured": MT.cohesion_fractured,
    "baseline": MT.cohesion_baseline,
    "exceptional": MT.cohesion_exceptional,
}
COHESION_CLASSES = frozenset(_COHESION)
ENDURANCE_CLASSES = frozenset({"hardened", "comfortable"})
PERCEPTION_MODES = frozenset({"ledger", "lens", "none"})


@dataclass(frozen=True)
class MTActor:
    """One actor's inputs: raw position/salience/capability + the four coded flags (§2, §5)."""

    position: float  # p_i (0-100)
    salience: float  # s_i (0-100)
    capability: float  # c_i (0-100)
    cohesion: str  # h_i ∈ {fractured, baseline, exceptional}
    endurance: str  # e_i ∈ {hardened, comfortable}
    loss: bool  # L_i ∈ {0, 1}
    perception: str  # m_i ∈ {ledger, lens, none}

    def __post_init__(self) -> None:
        if self.cohesion not in COHESION_CLASSES:
            raise ValueError(f"cohesion {self.cohesion!r} not in {sorted(COHESION_CLASSES)}")
        if self.endurance not in ENDURANCE_CLASSES:
            raise ValueError(f"endurance {self.endurance!r} not in {sorted(ENDURANCE_CLASSES)}")
        if self.perception not in PERCEPTION_MODES:
            raise ValueError(f"perception {self.perception!r} not in {sorted(PERCEPTION_MODES)}")


def _adjusted_salience(actor: MTActor, horizon_months: int | None) -> float:
    """Steps 1-2: loss intensity (capped at 100), then comfort decay for comfortable actors."""
    s = actor.salience
    if actor.loss:  # 1. loss intensity
        s = min(MT.salience_cap, s * MT.loss_intensity)
    if (  # 2. comfort decay — hardened actors never decay
        horizon_months is not None
        and horizon_months >= MT.decay_horizon_months
        and actor.endurance == "comfortable"
    ):
        s = s * MT.comfort_decay
    return s


def _adjusted_capability(actor: MTActor) -> float:
    """Step 3: cohesion multiplier on capability (not salience — capability is not capped)."""
    return actor.capability * _COHESION[actor.cohesion]


def adjusted_mean(actors: list[MTActor], horizon_months: int | None) -> float:
    """Step 4: WM' = Σ p·c·s / Σ c·s over the loss/decay/cohesion-adjusted values."""
    weights = [_adjusted_capability(a) * _adjusted_salience(a, horizon_months) for a in actors]
    total = sum(weights)
    if total <= 0:  # degenerate guard (mirrors the compromise mean): plain position mean
        return sum(a.position for a in actors) / len(actors)
    return sum(w * a.position for w, a in zip(weights, actors, strict=True)) / total


def trap_active(actors: list[MTActor]) -> bool:
    """The Grape Trap fires iff the stronger principal codes ledger and the weaker codes lens."""
    principals = [a for a in actors if a.perception in ("ledger", "lens")]
    if len(principals) < 2:
        return False
    stronger = max(principals, key=lambda a: a.capability)
    weaker = min(principals, key=lambda a: a.capability)
    return stronger.perception == "ledger" and weaker.perception == "lens"


def status_quo_lambda(actors: list[MTActor], vulnerability: bool, guarantor: bool) -> float:
    """Step 5's λ = min(0.40, 0.25·[V=1 and G=0] + 0.15·[trap active])."""
    guarantee = MT.guarantee_pull if (vulnerability and not guarantor) else 0.0
    trap = MT.trap_pull if trap_active(actors) else 0.0
    return min(MT.lambda_cap, guarantee + trap)


def model_three_forecast(
    actors: list[MTActor],
    *,
    reference_point: float | None,
    horizon_months: int | None,
    vulnerability: bool,
    guarantor: bool,
) -> float:
    """MT-1.0's settlement forecast (specs/MT-1.0.md §3), the five adjustments in the stated order.

    With no codable reference point the λ-terms are inactive and the prediction is the adjusted mean
    WM' (recorded as such); otherwise WM' is pulled toward the status quo by λ.
    """
    if not actors:
        raise ValueError("model-three needs at least one actor")
    wm = adjusted_mean(actors, horizon_months)
    if reference_point is None:  # no-rp fallback (§3.5): prediction = WM'
        return wm
    lam = status_quo_lambda(actors, vulnerability, guarantor)
    return (1.0 - lam) * wm + lam * reference_point
