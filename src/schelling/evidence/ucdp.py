"""UCDP reference-class client (Session 52, item 2, D52).

The Uppsala Conflict Data Program is the reference source for organized-violence base rates. This
client queries the UCDP API for a reference class — events in a country/window, optionally by
violence type — and returns a *summary* claim (how many events, how many fatalities) plus the events
themselves as candidate claims. The outside view uses these to say "of N comparable episodes, k
did X"; nothing here is placed on a continuum.

**Portal token now required.** Checked 2026-08-14: the UCDP API returns ``HTTP 401 — "API token
required. Add header: x-ucdp-access-token: <your-token>"``. Earlier releases were keyless; this
client sends the token when one is supplied (``UCDP_ACCESS_TOKEN``) and, when it is absent, reports
the source unavailable rather than degrading silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from schelling.evidence.claim import EvidenceClaim
from schelling.evidence.http import FetchSession

_API = "https://ucdpapi.pcr.uu.se/api"
_TOKEN_HEADER = "x-ucdp-access-token"


@dataclass(frozen=True)
class UCDPReferenceClass:
    """A UCDP reference class: its summary claim plus the event candidates behind it."""

    resource: str
    query: str
    total_count: int
    total_fatalities: int
    summary: EvidenceClaim  # value = total_count; the base-rate denominator
    events: list[EvidenceClaim]  # candidate event records (value = each event's best fatality est.)


def _event_claim(session: FetchSession, ev: dict[str, Any]) -> EvidenceClaim:
    eid = str(ev.get("id", ""))
    best = ev.get("best")
    country = str(ev.get("country", ""))
    when = str(ev.get("date_start", "") or ev.get("year", ""))[:10]
    conflict = str(ev.get("conflict_name", "") or ev.get("dyad_name", ""))
    return EvidenceClaim(
        provider="ucdp",
        identifier=f"gedevent:{eid}",
        title=f"{country}: {conflict}".strip(": ") or f"UCDP event {eid}",
        retrieved_at=session.today,
        value=float(best) if isinstance(best, int | float) else None,
        unit="fatalities (best estimate)" if isinstance(best, int | float) else "",
        period=when,
        url="https://ucdp.uu.se/",
        note="candidate reference-class event; a human ratifies before it counts",
    )


def ucdp_reference_class(
    session: FetchSession,
    *,
    token: str,
    resource: str = "gedevents",
    version: str = "24.1",
    country: str = "",
    start_date: str = "",
    end_date: str = "",
    type_of_violence: str = "",
    pagesize: int = 50,
) -> UCDPReferenceClass:
    """Query a UCDP reference class; requires a portal ``token`` (``UCDP_ACCESS_TOKEN``).

    Raises ``ValueError`` when ``token`` is blank, so the caller reports the source unavailable with
    the registration step rather than making a doomed request.
    """
    if not token.strip():
        raise ValueError(
            "UCDP requires a portal access token (x-ucdp-access-token); set UCDP_ACCESS_TOKEN "
            "(request one at https://ucdp.uu.se/apidocs/)"
        )
    params: dict[str, str] = {"pagesize": str(pagesize)}
    if country:
        params["Country"] = country
    if start_date:
        params["StartDate"] = start_date
    if end_date:
        params["EndDate"] = end_date
    if type_of_violence:
        params["type_of_violence"] = type_of_violence
    url = f"{_API}/{resource}/{version}?{urlencode(params)}"
    data = session.fetch_json(url, headers={_TOKEN_HEADER: token})
    results = data.get("Result", []) if isinstance(data, dict) else []
    total_count = int(data.get("TotalCount", len(results))) if isinstance(data, dict) else 0
    events = [_event_claim(session, ev) for ev in results]
    total_fatalities = sum(
        int(ev.get("best", 0) or 0) for ev in results if isinstance(ev.get("best"), int | float)
    )
    query = ", ".join(f"{k}={v}" for k, v in params.items() if k != "pagesize") or "all"
    summary = EvidenceClaim(
        provider="ucdp",
        identifier=f"{resource}/{version}?{urlencode(params)}",
        title=f"UCDP {resource} reference class ({query})",
        retrieved_at=session.today,
        value=float(total_count),
        unit="events",
        period=f"{start_date}..{end_date}".strip("."),
        url="https://ucdp.uu.se/",
        note=f"{total_fatalities} best-estimate fatalities across {len(results)} returned "
        f"of {total_count} total; a base-rate denominator, human ratifies",
    )
    return UCDPReferenceClass(
        resource=resource,
        query=query,
        total_count=total_count,
        total_fatalities=total_fatalities,
        summary=summary,
        events=events,
    )
