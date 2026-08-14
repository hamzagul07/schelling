"""ACLED reference-class client (Session 52, item 2, D52).

ACLED (Armed Conflict Location & Event Data) is the disaggregated political-violence and protest
event source. Like UCDP this client returns a reference-class summary (event count, fatalities) plus
the events as candidate claims — never a coordinate.

**Behind a key, with a registration step.** ACLED requires an API key and the registered email
(``ACLED_API_KEY`` + ``ACLED_EMAIL``; register at https://developer.acleddata.com/). When either is
absent the client reports the source unavailable rather than degrading silently — the item-2 rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from schelling.evidence.claim import EvidenceClaim
from schelling.evidence.http import FetchSession

_API = "https://api.acleddata.com/acled/read"


@dataclass(frozen=True)
class ACLEDReferenceClass:
    """An ACLED reference class: its summary claim plus the event candidates behind it."""

    query: str
    count: int
    total_fatalities: int
    summary: EvidenceClaim  # value = event count
    events: list[EvidenceClaim]  # candidate event records (value = fatalities each)


def _event_claim(session: FetchSession, ev: dict[str, Any]) -> EvidenceClaim:
    eid = str(ev.get("data_id", "") or ev.get("event_id_cnty", ""))
    fatal = ev.get("fatalities")
    fatal_n: int | None = None
    if isinstance(fatal, int | float) or (
        isinstance(fatal, str) and fatal.strip().lstrip("-").isdigit()
    ):
        fatal_n = int(fatal)
    etype = str(ev.get("event_type", ""))
    country = str(ev.get("country", ""))
    return EvidenceClaim(
        provider="acled",
        identifier=f"acled:{eid}",
        title=f"{country}: {etype}".strip(": ") or f"ACLED event {eid}",
        retrieved_at=session.today,
        value=float(fatal_n) if fatal_n is not None else None,
        unit="fatalities" if fatal_n is not None else "",
        period=str(ev.get("event_date", ""))[:10],
        url=str(ev.get("source", "") or "https://acleddata.com/"),
        note="candidate reference-class event; a human ratifies before it counts",
    )


def acled_reference_class(
    session: FetchSession,
    *,
    key: str,
    email: str,
    country: str = "",
    start_date: str = "",
    end_date: str = "",
    event_type: str = "",
    limit: int = 50,
) -> ACLEDReferenceClass:
    """Query an ACLED reference class; requires ``key`` + ``email`` (ACLED_API_KEY / ACLED_EMAIL).

    Raises ``ValueError`` when either credential is blank, so the caller reports the source
    unavailable with the registration step rather than making a doomed request.
    """
    if not key.strip() or not email.strip():
        raise ValueError(
            "ACLED requires an API key and the registered email; set ACLED_API_KEY and ACLED_EMAIL "
            "(register at https://developer.acleddata.com/)"
        )
    params: dict[str, str] = {"key": key, "email": email, "limit": str(limit)}
    if country:
        params["country"] = country
    if start_date and end_date:
        params["event_date"] = f"{start_date}|{end_date}"
        params["event_date_where"] = "BETWEEN"
    if event_type:
        params["event_type"] = event_type
    data = session.fetch_json(f"{_API}?{urlencode(params)}")
    rows = data.get("data", []) if isinstance(data, dict) else []
    count = int(data.get("count", len(rows))) if isinstance(data, dict) else 0
    events = [_event_claim(session, ev) for ev in rows]
    total_fatalities = sum(
        int(ev.get("fatalities", 0) or 0)
        for ev in rows
        if str(ev.get("fatalities", "")).lstrip("-").isdigit()
    )
    # the key never appears in the citation identifier — provenance, not a secret leak
    ident_params = {k: v for k, v in params.items() if k not in ("key", "email")}
    query = ", ".join(f"{k}={v}" for k, v in ident_params.items() if k != "limit") or "all"
    summary = EvidenceClaim(
        provider="acled",
        identifier=f"acled/read?{urlencode(ident_params)}",
        title=f"ACLED reference class ({query})",
        retrieved_at=session.today,
        value=float(count),
        unit="events",
        period=f"{start_date}..{end_date}".strip("."),
        url="https://acleddata.com/",
        note=f"{total_fatalities} fatalities across {len(rows)} returned events; a base-rate "
        f"denominator, human ratifies",
    )
    return ACLEDReferenceClass(
        query=query,
        count=count,
        total_fatalities=total_fatalities,
        summary=summary,
        events=events,
    )
