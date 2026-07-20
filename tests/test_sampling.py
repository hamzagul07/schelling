"""Tests for triangular sampling (BUILD_PLAN §6)."""

from __future__ import annotations

from schelling.mc.sampling import derive_rng, sample_game, sample_triangular
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import TriangularEstimate


def test_point_estimate_passes_through_unchanged() -> None:
    rng = derive_rng(0, 0)
    point = TriangularEstimate.point(42.0)
    assert all(sample_triangular(point, rng) == 42.0 for _ in range(100))


def test_draw_stays_within_range() -> None:
    rng = derive_rng(123, 0)
    est = TriangularEstimate(low=2.0, mode=4.0, high=7.0)
    for _ in range(1000):
        v = sample_triangular(est, rng)
        assert 2.0 <= v <= 7.0


def test_derive_rng_is_deterministic_and_draw_dependent() -> None:
    est = TriangularEstimate(low=0.0, mode=5.0, high=10.0)
    a = sample_triangular(est, derive_rng(99, 3))
    b = sample_triangular(est, derive_rng(99, 3))
    c = sample_triangular(est, derive_rng(99, 4))
    assert a == b  # same (seed, draw) -> same value
    assert a != c  # different draw -> different stream


def test_sample_game_produces_point_estimates_and_preserves_structure(
    toy_game: GameSpec,
) -> None:
    sampled = sample_game(toy_game, derive_rng(1, 0))
    assert [a.id for a in sampled.actors] == [a.id for a in toy_game.actors]
    assert sampled.question_id == toy_game.question_id
    for actor in sampled.actors:
        assert actor.position.is_point
        assert actor.salience.is_point
        assert actor.capability.is_point


def test_point_estimate_game_has_zero_variance(toy_game: GameSpec) -> None:
    # Every field of the toy game is a point, so all draws are identical.
    a = sample_game(toy_game, derive_rng(5, 0))
    b = sample_game(toy_game, derive_rng(5, 999))
    assert a.model_dump_json() == b.model_dump_json()
