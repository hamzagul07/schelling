"""Institutional archive fetcher — the precedent denominator (Session 52, item 3, D52).

Given a body (IAEA, OPEC, EU) and a date range, enumerate that body's *published* session and
statement records as candidates. This feeds the PRECEDENT layer's sessions-at-risk denominator (the
D30.2 rule): to say "a resolution passed in k of the last N Board meetings" you first need the list
of the N meetings, sourced from the body itself. Every entry is an :class:`EvidenceClaim` (kind
``archive``); nothing is placed on a continuum and nothing is ratified — a human does that.

The fetcher parses RSS and Atom feeds (the clean, machine-readable case) via the standard library.
Some bodies bot-block their pages; when a body's feed is unreachable the caller sees a normal
``FetchError`` and reports the body *unavailable* — never a fabricated list. A ``--url`` override
lets a human point the fetcher at any feed they can reach.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from schelling.evidence.claim import EvidenceClaim
from schelling.evidence.http import FetchSession

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}


@dataclass(frozen=True)
class ArchiveSource:
    """A body's published-record feed: where it is and whether a machine feed is known to work."""

    body: str
    name: str
    url: str
    live_verified: bool  # True when a keyless feed was confirmed reachable + parseable


# Presets. IAEA publishes a working RSS feed (verified 2026-08-14). OPEC and the EU Council publish
# their releases as bot-protected HTML with no open feed, so their presets point at the human-facing
# listing and the fetcher reports them unavailable live until a reachable --url is supplied.
ARCHIVE_SOURCES: dict[str, ArchiveSource] = {
    "iaea": ArchiveSource(
        body="iaea",
        name="IAEA press releases and statements",
        url="https://www.iaea.org/feeds/topnews",
        live_verified=True,
    ),
    "opec": ArchiveSource(
        body="opec",
        name="OPEC press releases",
        url="https://www.opec.org/opec_web/en/press_room/press_releases.htm",
        live_verified=False,
    ),
    "eu": ArchiveSource(
        body="eu",
        name="Council of the EU press releases",
        url="https://www.consilium.europa.eu/en/press/press-releases/",
        live_verified=False,
    ),
}


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _normalize_date(raw: str) -> str:
    """Best-effort ISO ``YYYY-MM-DD`` from the several date shapes feeds use (empty if unparseable).

    Handles RFC-822 ('Wed, 12 Aug 2026 12:44:00 GMT'), ISO ('2026-08-12…'), and the IAEA feed's
    non-standard 'YY-MM-DD  HH:MM'. An unrecognised date returns '' — the entry is still enumerated,
    flagged as undated, never dropped.
    """
    s = " ".join(raw.split())  # collapse the stray whitespace/newlines IAEA emits
    if not s:
        return ""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)  # ISO
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{2})-(\d{2})-(\d{2})\b", s)  # IAEA 'YY-MM-DD'
    if m:
        return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", s)  # '12 Aug 2026' (RFC-822-ish)
    if m and m.group(2)[:3].title() in _MONTHS:
        return f"{m.group(3)}-{_MONTHS[m.group(2)[:3].title()]:02d}-{int(m.group(1)):02d}"
    return ""


@dataclass(frozen=True)
class _Entry:
    title: str
    link: str
    date_iso: str


def _parse_feed(xml_text: str) -> list[_Entry]:
    """Parse an RSS or Atom feed into (title, link, iso-date) entries (auto-detecting which)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"archive feed is not valid XML (RSS/Atom expected): {exc}") from exc
    entries: list[_Entry] = []
    items = root.findall(".//item")  # RSS 2.0
    if items:
        for it in items:
            entries.append(
                _Entry(
                    title=_text(it.find("title")),
                    link=_text(it.find("link")),
                    date_iso=_normalize_date(_text(it.find("pubDate")) or _text(it.find("date"))),
                )
            )
        return entries
    ns = "{http://www.w3.org/2005/Atom}"  # Atom
    for e in root.findall(f".//{ns}entry"):
        link_el = e.find(f"{ns}link")
        href = link_el.get("href") if link_el is not None else ""
        entries.append(
            _Entry(
                title=_text(e.find(f"{ns}title")),
                link=href or "",
                date_iso=_normalize_date(
                    _text(e.find(f"{ns}updated")) or _text(e.find(f"{ns}published"))
                ),
            )
        )
    return entries


def _in_window(date_iso: str, since: str, until: str) -> bool:
    if (
        not date_iso
    ):  # undated entries are kept — the human decides, they are never silently dropped
        return True
    if since and date_iso < since:
        return False
    return not (until and date_iso > until)


def archive_enumerate(
    session: FetchSession,
    body: str,
    *,
    since: str = "",
    until: str = "",
    url: str = "",
) -> list[EvidenceClaim]:
    """Enumerate a body's published records in ``[since, until]`` as candidate claims (D30.2).

    ``body`` selects a preset (iaea/opec/eu) or, with ``url``, any feed a human can reach. Each
    entry becomes an ``EvidenceClaim`` (provider ``<body>-archive``); the value is ``None`` — these
    are records to count, not numbers. Undated entries are kept and flagged. Raises ``ValueError``
    for an unknown body with no ``url``.
    """
    feed_url = url
    source_name = f"{body} feed"
    if not feed_url:
        src = ARCHIVE_SOURCES.get(body)
        if src is None:
            raise ValueError(
                f"unknown archive body {body!r}; known: {', '.join(ARCHIVE_SOURCES)} "
                f"(or pass an explicit --url)"
            )
        feed_url, source_name = src.url, src.name
    text = session.fetch_text(feed_url)  # FetchError here => caller reports the body unavailable
    claims: list[EvidenceClaim] = []
    for e in _parse_feed(text):
        if not _in_window(e.date_iso, since, until):
            continue
        undated = "" if e.date_iso else " (date unparsed — verify by hand)"
        claims.append(
            EvidenceClaim(
                provider=f"{body}-archive",
                identifier=e.link or e.title,
                title=e.title,
                retrieved_at=session.today,
                value=None,  # a record, not a datum
                period=e.date_iso,
                url=e.link,
                note=f"candidate {source_name} record; a human ratifies before it counts{undated}",
            )
        )
    return claims
