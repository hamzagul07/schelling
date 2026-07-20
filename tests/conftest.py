"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schelling.schemas.question import GameSpec

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def toy_game() -> GameSpec:
    """The 3-actor toy game with hand-computable mean (27.6923...) and median (20)."""
    data = json.loads((FIXTURES / "toy_3actor.json").read_text())
    return GameSpec.model_validate(data)
