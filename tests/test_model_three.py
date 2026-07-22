"""Golden tests for Model Three / Asabiyyah (MT-1.0), against specs/MT-1.0.md §3.

Every term is exercised firing alone and composed, against an INDEPENDENT hand-computation of
the spec's pipeline (the spec's literal constants are written into the test arithmetic, so the
test fails if the code drifts from them). Determinism is pinned. These are synthetic fixtures
only — MT-1.0 is
never run against the real library before its 8-verified-case reading.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from schelling.backtest.model_three import (
    SPEC_CONSTANTS,
    MTActor,
    adjusted_mean,
    model_three_forecast,
    status_quo_lambda,
    trap_active,
)

SPEC = Path(__file__).parent.parent / "specs" / "MT-1.0.md"


def _actor(
    p: float,
    s: float,
    c: float,
    *,
    cohesion: str = "baseline",
    endurance: str = "comfortable",
    loss: bool = False,
    perception: str = "none",
) -> MTActor:
    return MTActor(p, s, c, cohesion, endurance, loss, perception)


# --------------------------------------------------------------- constants match the spec (item 2)
def test_constants_match_spec_character_for_character() -> None:
    spec_text = SPEC.read_text()
    for literal, value in SPEC_CONSTANTS:
        assert literal in spec_text, f"{literal!r} not found verbatim in {SPEC}"
        assert float(literal.split()[0]) == value  # the code constant equals the spec literal


# --------------------------------------------------------------- each term firing alone
def test_loss_intensity_alone_multiplies_salience_by_1_15() -> None:
    # actor A (position 0) gets a loss boost, so the mean is pulled toward 0 vs no-loss.
    a_loss = [_actor(0, 50, 100, loss=True), _actor(100, 50, 100)]
    a_none = [_actor(0, 50, 100), _actor(100, 50, 100)]
    wm_loss = adjusted_mean(a_loss, horizon_months=0)
    sA = 50 * 1.15
    assert wm_loss == pytest.approx(
        (0 * 100 * sA + 100 * 100 * 50) / (100 * sA + 100 * 50), abs=1e-9
    )
    assert wm_loss < adjusted_mean(a_none, horizon_months=0)  # loss pulls toward the loss-actor


def test_loss_intensity_is_capped_at_100() -> None:
    # salience 95 * 1.15 = 109.25 -> capped to 100; the actor then dominates as if s=100.
    capped = [_actor(0, 95, 100, loss=True), _actor(100, 95, 100)]
    assert adjusted_mean(capped, 0) == pytest.approx(
        (0 * 100 * 100 + 100 * 100 * 95) / (100 * 100 + 100 * 95), abs=1e-9
    )


def test_comfort_decay_only_at_long_horizon_and_only_comfortable() -> None:
    # A is comfortable, B is hardened, so only A can decay.
    comfortable = [
        _actor(0, 50, 100, endurance="comfortable"),
        _actor(100, 50, 100, endurance="hardened"),
    ]
    # T >= 18 -> comfortable actor A decays x0.80 -> weight shrinks -> mean moves toward B (100).
    wm_long = adjusted_mean(comfortable, horizon_months=24)
    sA = 50 * 0.80
    assert wm_long == pytest.approx(
        (0 * 100 * sA + 100 * 100 * 50) / (100 * sA + 100 * 50), abs=1e-9
    )
    # T < 18 -> no decay
    assert adjusted_mean(comfortable, horizon_months=12) == pytest.approx(50.0, abs=1e-9)
    # hardened never decays, even at long horizon
    hardened = [
        _actor(0, 50, 100, endurance="hardened"),
        _actor(100, 50, 100, endurance="hardened"),
    ]
    assert adjusted_mean(hardened, horizon_months=24) == pytest.approx(50.0, abs=1e-9)


def test_cohesion_multiplier_per_class() -> None:
    base = adjusted_mean([_actor(0, 50, 100), _actor(100, 50, 100)], 0)
    assert base == pytest.approx(50.0, abs=1e-9)  # baseline x1.00 -> symmetric
    exc = [_actor(0, 50, 100, cohesion="exceptional"), _actor(100, 50, 100)]
    assert adjusted_mean(exc, 0) == pytest.approx(
        (0 * (100 * 1.15) * 50 + 100 * 100 * 50) / ((100 * 1.15) * 50 + 100 * 50), abs=1e-9
    )
    frac = [_actor(0, 50, 100, cohesion="fractured"), _actor(100, 50, 100)]
    assert adjusted_mean(frac, 0) > 50.0  # A weakened -> mean toward B


# --------------------------------------------------------------- the status-quo pull (λ)
def _principals() -> list[MTActor]:
    # stronger (cap 90) codes ledger, weaker (cap 40) codes lens -> trap active
    return [_actor(20, 60, 90, perception="ledger"), _actor(80, 60, 40, perception="lens")]


def test_lambda_guarantee_pull_only() -> None:
    two = [_actor(20, 60, 90), _actor(80, 60, 40)]  # no trap (perception none)
    assert status_quo_lambda(two, vulnerability=True, guarantor=False) == pytest.approx(0.25)
    assert status_quo_lambda(two, vulnerability=True, guarantor=True) == 0.0  # guarantor present
    assert status_quo_lambda(two, vulnerability=False, guarantor=False) == 0.0  # no vulnerability


def test_lambda_trap_pull_only() -> None:
    assert status_quo_lambda(_principals(), vulnerability=False, guarantor=False) == pytest.approx(
        0.15
    )


def test_lambda_both_active_is_capped_at_0_40() -> None:
    # item 4: a trap-active no-guarantor case must show λ = 0.40 capped (0.25 + 0.15).
    assert status_quo_lambda(_principals(), vulnerability=True, guarantor=False) == 0.40


def test_trap_requires_stronger_ledger_and_weaker_lens() -> None:
    assert trap_active(_principals()) is True
    # reversed roles (stronger=lens, weaker=ledger) -> no trap
    reversed_roles = [
        _actor(20, 60, 90, perception="lens"),
        _actor(80, 60, 40, perception="ledger"),
    ]
    assert trap_active(reversed_roles) is False
    # only one principal coded -> no trap
    assert trap_active([_actor(20, 60, 90, perception="ledger"), _actor(80, 60, 40)]) is False


# --------------------------------------------------------------- fallback + composition
def test_no_reference_point_falls_back_to_adjusted_mean() -> None:
    actors = _principals()
    got = model_three_forecast(
        actors, reference_point=None, horizon_months=24, vulnerability=True, guarantor=False
    )
    assert got == pytest.approx(adjusted_mean(actors, 24), abs=1e-9)  # λ inactive with no rp


def test_composed_all_terms_golden() -> None:
    # Independent hand-computation of the full §3 pipeline with the spec's literal constants.
    strong = _actor(
        20, 60, 90, cohesion="exceptional", endurance="comfortable", loss=True, perception="ledger"
    )
    weak = _actor(
        80, 60, 40, cohesion="fractured", endurance="hardened", loss=False, perception="lens"
    )
    got = model_three_forecast(
        [strong, weak], reference_point=50.0, horizon_months=24, vulnerability=True, guarantor=False
    )
    s_s = min(100.0, 60 * 1.15) * 0.80  # loss (capped), then comfort decay
    c_s = 90 * 1.15  # exceptional cohesion
    s_w = 60.0  # no loss; hardened -> no decay
    c_w = 40 * 0.85  # fractured cohesion
    wm = (20 * c_s * s_s + 80 * c_w * s_w) / (c_s * s_s + c_w * s_w)
    lam = min(0.40, 0.25 + 0.15)  # V and not G, plus active trap -> capped
    assert got == pytest.approx((1 - lam) * wm + lam * 50.0, abs=1e-9)


def test_model_three_is_deterministic() -> None:
    actors = _principals()
    kw = dict(reference_point=50.0, horizon_months=24, vulnerability=True, guarantor=False)
    assert model_three_forecast(actors, **kw) == model_three_forecast(actors, **kw)  # type: ignore[arg-type]


def test_mtactor_rejects_unknown_flag_values() -> None:
    for bad in (
        dict(cohesion="strong"),
        dict(endurance="tired"),
        dict(perception="grievance"),
    ):
        with pytest.raises(ValueError):
            _actor(0, 50, 100, **bad)  # type: ignore[arg-type]
