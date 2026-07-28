"""GDELT client feeding the PRECEDENT layer only (Session 46, D46.2).

Given an actor pair / institution / event type and a date range, this returns candidate comparable
events — each a source URL, a date, and the CAMEO code the query targeted — as **proposals for
the precedent layer only**, never evidence-river material. Every candidate lands in an *unratified*
:class:`PrecedentSet` exactly like the LLM precedent finder's output: a human must set the real
placement, mark it ``ratified``, and quote a ratification before it can reach the reference-class
panel. Nothing GDELT returns is trusted automatically.

GDELT's coding is machine-generated from the global news stream, so its candidates carry the usual
auto-coding hazards — **duplicate** reports of one event, **circular** reporting (outlets citing
each other), and outright **erroneous** codings — documented in ``docs/PRECEDENTS.md`` and shown
in the panel. Ratification is what filters them. Queries go through the shared cached, budgeted,
injectable :class:`FetchSession`, so CI never calls GDELT live.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from schelling.evidence.http import FetchSession
from schelling.precedents.schemas import PrecedentSet
from schelling.schemas.forecast import Precedent

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_PLACEMENT_PENDING = 50.0  # neutral placeholder; the human sets the real placement at ratification


@dataclass(frozen=True)
class GdeltCandidate:
    """One GDELT candidate comparable event: a source, its date, and the CAMEO code queried for."""

    url: str
    title: str
    date: str  # YYYY-MM-DD
    cameo: str  # the CAMEO event code the query targeted (analyst-specified)
    domain: str


def _fmt_date(seendate: str) -> str:
    """GDELT ``seendate`` (e.g. ``20260715T120000Z``) -> ``YYYY-MM-DD``; empty stays empty."""
    digits = "".join(ch for ch in seendate if ch.isdigit())
    if len(digits) < 8:
        return seendate
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"


def gdelt_candidates(
    session: FetchSession,
    query: str,
    *,
    start_date: str,
    end_date: str,
    cameo: str = "",
    max_records: int = 25,
) -> list[GdeltCandidate]:
    """Fetch candidate comparable events from the GDELT DOC 2.0 API for ``query`` in the date range.

    ``query`` names the actors / institution / event in GDELT's article search; ``cameo`` is the
    event code the analyst is looking for (recorded on each candidate). Dates are ``YYYY-MM-DD``.
    """
    params = urlencode(
        {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max_records,
            "startdatetime": start_date.replace("-", "") + "000000",
            "enddatetime": end_date.replace("-", "") + "235959",
            "sort": "datedesc",
        }
    )
    data = session.fetch_json(f"{GDELT_DOC_URL}?{params}")
    out: list[GdeltCandidate] = []
    seen: set[str] = set()
    for art in data.get("articles", []):
        url = art.get("url")
        if (
            not url or url in seen
        ):  # first-pass dedup by URL (duplicates are the point of ratifying)
            continue
        seen.add(url)
        out.append(
            GdeltCandidate(
                url=url,
                title=art.get("title", "") or "",
                date=_fmt_date(art.get("seendate", "")),
                cameo=cameo,
                domain=art.get("domain", "") or "",
            )
        )
    return out


def candidates_to_precedent_set(
    candidates: list[GdeltCandidate], question_id: str, *, created_at: str | None = None
) -> PrecedentSet:
    """Wrap GDELT candidates as UNRATIFIED precedent proposals (D46.2).

    Each proposal's placement is a pending placeholder — GDELT locates a candidate event; the human
    codes where it sits on this question's continuum and ratifies it. The set stays unratified (no
    ``ratification_note``) so the panel will not use it until a human does that work.
    """
    precedents = [
        Precedent(
            id=f"gdelt-{i + 1:03d}",
            what_happened=c.title or f"GDELT candidate from {c.domain}",
            date=c.date,
            source=c.url,
            proposed_placement=_PLACEMENT_PENDING,
            reasoning=(
                f"GDELT candidate (CAMEO {c.cameo or 'n/a'}, {c.domain}) — machine-coded; "
                "PLACEMENT PENDING human coding and ratification"
            ),
            ex_ante_codable=True,  # GDELT codes from contemporaneous reports
            ratified=False,
        )
        for i, c in enumerate(candidates)
    ]
    return PrecedentSet(
        question_id=question_id,
        precedents=precedents,
        source_model="gdelt",
        created_at=created_at,
        reference_class="",  # the human defines the reference class when ratifying
        ratification_note="",  # unratified — the panel will not use these until a human ratifies
    )
