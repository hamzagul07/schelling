"""Power indices (Session 40, D40.2), checked against published worked examples so correctness is
externally verifiable: the 1958 EEC Council of Ministers and the UN Security Council.

Sources for the target figures:
* EEC-6 — weights [4,4,4,2,2,1], quota 12: the canonical Shapley-Shubik values are 0.2333 for the
  three large members, 0.15 for the two medium, 0 for Luxembourg (a dummy); normalized Banzhaf is
  10/42, 6/42, 0 (raw swing counts 10, 6, 0). Straffin, *Game Theory and Strategy* (1993).
* UNSC — five permanent members (weight 7) + ten elected (weight 1), quota 39: Shapley-Shubik is
  0.19627 per permanent member and 0.001865 per elected member.
"""

from __future__ import annotations

import pytest

from schelling.power.indices import BANZHAF, SHAPLEY_SHUBIK, compute_power

EEC6_WEIGHTS = [4, 4, 4, 2, 2, 1]
EEC6_QUOTA = 12
EEC6_LABELS = ["FR", "DE", "IT", "BE", "NL", "LU"]

UNSC_WEIGHTS = [7] * 5 + [1] * 10
UNSC_QUOTA = 39


# --------------------------------------------------------------- EEC-6 (exact, published values)
def test_eec6_shapley_shubik_matches_published() -> None:
    r = compute_power(EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS)[SHAPLEY_SHUBIK]
    assert r.method == "exact"
    assert r.indices[:3] == pytest.approx([14 / 60, 14 / 60, 14 / 60])  # 0.2333 each
    assert r.indices[3:5] == pytest.approx([9 / 60, 9 / 60])  # 0.15 each
    assert r.indices[5] == pytest.approx(0.0)
    assert sum(r.indices) == pytest.approx(1.0)
    assert r.dummies == ["LU"]


def test_eec6_banzhaf_matches_published() -> None:
    r = compute_power(EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS)[BANZHAF]
    # raw swings 10,10,10,6,6,0 -> total 42 -> normalized 10/42, 6/42, 0
    assert r.indices[:3] == pytest.approx([10 / 42, 10 / 42, 10 / 42])
    assert r.indices[3:5] == pytest.approx([6 / 42, 6 / 42])
    assert r.indices[5] == pytest.approx(0.0)
    assert sum(r.indices) == pytest.approx(1.0)


# --------------------------------------------------------------- UNSC (exact, published values)
def test_unsc_shapley_shubik_matches_published() -> None:
    r = compute_power(UNSC_WEIGHTS, UNSC_QUOTA)[SHAPLEY_SHUBIK]
    perm = r.indices[:5]
    elected = r.indices[5:]
    assert perm == pytest.approx([0.19627] * 5, abs=5e-5)
    assert elected == pytest.approx([0.001865] * 10, abs=5e-5)
    assert sum(r.indices) == pytest.approx(1.0)
    assert not r.dummies  # an elected member has small but non-zero power


def test_unsc_banzhaf_structure_holds() -> None:
    r = compute_power(UNSC_WEIGHTS, UNSC_QUOTA)[BANZHAF]
    perm = r.indices[:5]
    elected = r.indices[5:]
    assert perm == pytest.approx([perm[0]] * 5)  # all permanent equal
    assert elected == pytest.approx([elected[0]] * 10)  # all elected equal
    assert perm[0] > elected[0] > 0.0
    assert sum(r.indices) == pytest.approx(1.0)


# --------------------------------------------------------------- dummies, blocs, and MC path
def test_dictator_and_dummies() -> None:
    # weight 3 meets the quota alone; the two weight-1 players never swing -> dummies
    r = compute_power([3, 1, 1], 3, labels=["boss", "x", "y"])[SHAPLEY_SHUBIK]
    assert r.indices == pytest.approx([1.0, 0.0, 0.0])
    assert set(r.dummies) == {"x", "y"}


def test_blocs_merge_into_one_player() -> None:
    r = compute_power(EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS, blocs=[["BE", "NL"]])[
        SHAPLEY_SHUBIK
    ]
    assert r.labels[0] == "BE+NL"  # the bloc is one player, listed first
    assert r.weights[0] == 4  # 2 + 2
    assert len(r.labels) == 5  # six players, two collapsed into one
    assert sum(r.indices) == pytest.approx(1.0)


def test_bloc_member_cannot_appear_twice() -> None:
    with pytest.raises(ValueError, match="more than one bloc"):
        compute_power(EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS, blocs=[["FR"], ["FR", "DE"]])


def test_quota_above_total_weight_is_rejected() -> None:
    with pytest.raises(ValueError, match="exceeds total weight"):
        compute_power([1, 1, 1], 4)


def test_monte_carlo_matches_exact_and_is_deterministic() -> None:
    exact = compute_power(EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS)[SHAPLEY_SHUBIK]
    # force the sampling path on this small game by lowering the exact threshold
    mc = compute_power(
        EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS, seed=7, samples=40_000, exact_max_n=1
    )[SHAPLEY_SHUBIK]
    assert mc.method == "monte-carlo"
    assert mc.standard_error is not None
    assert mc.indices == pytest.approx(exact.indices, abs=0.01)  # within sampling error
    # same seed -> byte-identical estimate (CLAUDE.md rule 2)
    mc2 = compute_power(
        EEC6_WEIGHTS, EEC6_QUOTA, labels=EEC6_LABELS, seed=7, samples=40_000, exact_max_n=1
    )[SHAPLEY_SHUBIK]
    assert mc.indices == mc2.indices
    assert mc.standard_error == mc2.standard_error
