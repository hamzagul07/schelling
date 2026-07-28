"""Metaculus crowd baseline (Session 46, D46.3).

Query the Metaculus API for questions matching a sealed question's topic and window, so a human can
judge whether any is a *genuine* comparator. Matching is never automatic: the search returns
candidates for inspection, and a record is built only for an id the analyst names, with a written
justification attached. The resulting :class:`CrowdForecastRecord` (``model = "crowd-metaculus"``)
seals on the ledger exactly like the llm-judgment baseline — the community forecast is external and
non-reproducible, so its commitment is the record file's SHA-256.

All requests go through the shared cached/budgeted/injectable :class:`FetchSession`, so CI never
calls Metaculus live.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from schelling.evidence.http import FetchSession
from schelling.schemas.forecast import CrowdForecastRecord, Ensemble
from schelling.schemas.question import GameSpec

_API = "https://www.metaculus.com/api2/questions/"


@dataclass(frozen=True)
class MetaculusMatch:
    """One candidate Metaculus question for human inspection (never an automatic match)."""

    metaculus_id: int
    title: str
    url: str
    community_prediction: float | None  # community median (probability 0-1, or a scaled value)
    n_forecasters: int
    close_time: str


def _community(question: dict[str, Any]) -> float | None:
    """Pull the community median from a few known API shapes; None if unavailable."""
    cp = question.get("community_prediction")
    if isinstance(cp, int | float):
        return float(cp)
    if isinstance(cp, dict):
        full = cp.get("full")
        if isinstance(full, dict) and isinstance(full.get("q2"), int | float):
            return float(full["q2"])
    return None


def _one(question: dict[str, Any]) -> MetaculusMatch:
    qid = int(question.get("id", 0))
    return MetaculusMatch(
        metaculus_id=qid,
        title=str(question.get("title", "")),
        url=str(question.get("url") or f"https://www.metaculus.com/questions/{qid}/"),
        community_prediction=_community(question),
        n_forecasters=int(question.get("number_of_forecasters", 0) or 0),
        close_time=str(question.get("scheduled_close_time") or question.get("close_time") or ""),
    )


def metaculus_search(
    session: FetchSession, topic: str, *, close_after: str = "", close_before: str = ""
) -> list[MetaculusMatch]:
    """Search Metaculus for questions matching ``topic`` (+ optional window) — candidates only."""
    params: dict[str, str] = {"search": topic, "order_by": "-activity", "limit": "10"}
    if close_after:
        params["close_time__gt"] = close_after
    if close_before:
        params["close_time__lt"] = close_before
    data = session.fetch_json(f"{_API}?{urlencode(params)}")
    results = data.get("results", data if isinstance(data, list) else [])
    return [_one(q) for q in results]


def metaculus_question(session: FetchSession, metaculus_id: int) -> MetaculusMatch:
    """Fetch a single Metaculus question by id (the match the analyst chose)."""
    data = session.fetch_json(f"{_API}{metaculus_id}/")
    return _one(data)


def build_crowd_record(
    game: GameSpec,
    match: MetaculusMatch,
    *,
    placement: float,
    justification: str,
    created_at: str | None = None,
) -> CrowdForecastRecord:
    """Build a sealable crowd record from a chosen match + a human ``justification`` (D46.3).

    ``placement`` is the community forecast placed on the question's 0-100 continuum by the analyst
    (a binary community probability maps to ``prob * 100`` by default). Raises if ``justification``
    is blank — the match must be justified in writing before a record exists.
    """
    if not justification.strip():
        raise ValueError("a crowd match must be justified in writing (justification is empty)")
    ident = json.dumps({"q": game.question_id, "m": match.metaculus_id}, sort_keys=True)
    inputs_hash = hashlib.sha256(ident.encode("utf-8")).hexdigest()
    return CrowdForecastRecord(
        question_id=game.question_id,
        run_id=f"{game.question_id}-crowd-metaculus-{match.metaculus_id}",
        inputs_hash=inputs_hash,
        created_at=created_at,
        metaculus_id=match.metaculus_id,
        metaculus_url=match.url,
        community_prediction=match.community_prediction,
        n_forecasters=match.n_forecasters,
        match_justification=justification.strip(),
        ensemble=Ensemble(
            median=placement,
            mean=placement,
            p10=placement,
            p90=placement,
            n_draws=match.n_forecasters,
        ),
        game=game,
    )
