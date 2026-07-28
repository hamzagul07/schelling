"""Scholarly open-version lookup for case-library acquisition (Session 46, D46.4).

A read-only aid: given a citation (a DOI or a title), find open-access versions via OpenAlex
and, for a DOI, Unpaywall. It returns links for a human to follow — it never ingests anything into
the case library or the evidence river automatically. Requests go through the shared
cached/budgeted/injectable :class:`FetchSession`, so CI never calls the services live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote, urlencode

from schelling.evidence.http import FetchSession

_OPENALEX = "https://api.openalex.org/works"
_UNPAYWALL = "https://api.unpaywall.org/v2"


@dataclass(frozen=True)
class OpenVersion:
    """One open-access location for a work: a URL and where it was found."""

    url: str
    source: str  # "openalex" | "unpaywall"
    kind: str = ""  # e.g. "publishedVersion", "acceptedVersion", landing/pdf


@dataclass(frozen=True)
class LiteratureResult:
    """A work and any open versions found for it (read-only)."""

    query: str
    title: str
    doi: str
    is_open: bool
    versions: list[OpenVersion] = field(default_factory=list)


def _looks_like_doi(citation: str) -> str:
    c = citation.strip()
    for marker in ("doi.org/", "doi:"):
        if marker in c:
            c = c.split(marker, 1)[1]
    return c if c.startswith("10.") else ""


def _openalex_versions(work: dict[str, object]) -> list[OpenVersion]:
    versions: list[OpenVersion] = []
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        url = best.get("pdf_url") or best.get("landing_page_url")
        if isinstance(url, str) and url:
            versions.append(
                OpenVersion(url=url, source="openalex", kind=str(best.get("version", "")))
            )
    return versions


def literature_lookup(session: FetchSession, citation: str, *, email: str = "") -> LiteratureResult:
    """Find open versions of ``citation`` (DOI or title) via OpenAlex (+ Unpaywall for a DOI)."""
    doi = _looks_like_doi(citation)
    if doi:
        work = session.fetch_json(f"{_OPENALEX}/https://doi.org/{quote(doi)}")
    else:
        data = session.fetch_json(f"{_OPENALEX}?{urlencode({'search': citation, 'per-page': 1})}")
        results = data.get("results", []) if isinstance(data, dict) else []
        work = results[0] if results else {}
    title = str(work.get("title", "")) if work else ""
    resolved_doi = doi or _looks_like_doi(str(work.get("doi", ""))) if work else doi
    versions = _openalex_versions(work) if work else []
    if resolved_doi and email:
        try:
            up = session.fetch_json(
                f"{_UNPAYWALL}/{quote(resolved_doi)}?{urlencode({'email': email})}"
            )
        except Exception:  # Unpaywall is a best-effort supplement, never fatal
            up = {}
        loc = up.get("best_oa_location") if isinstance(up, dict) else None
        if isinstance(loc, dict):
            url = loc.get("url_for_pdf") or loc.get("url")
            if isinstance(url, str) and url:
                versions.append(
                    OpenVersion(url=url, source="unpaywall", kind=str(loc.get("version", "")))
                )
    return LiteratureResult(
        query=citation,
        title=title,
        doi=resolved_doi,
        is_open=bool(versions),
        versions=versions,
    )
