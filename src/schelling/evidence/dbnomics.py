"""DBnomics indicator client — capability & salience sourcing (Session 52, item 1, D52).

DBnomics aggregates official statistical providers (IMF, World Bank, Eurostat, OECD, national
statistics offices, …) behind one free, keyless API. This client walks the natural path
**search → dataset → series**: find datasets matching a query, list the series inside one, then pull
a series' observations. The latest observation becomes an :class:`EvidenceClaim` carrying the
provider, the exact series id, the value, its period, and the retrieval date.

The purpose is to *source* the numbers behind a capability or salience coordinate — a country's
fiscal breakeven oil price, its production weight, its budget dependence on a commodity, its GDP —
so that when a human or the formalizer places an actor, the placement cites a real series rather
than a guess. This client never writes a coordinate; it supplies a citation.

Every request goes through the shared cached/budgeted/injectable :class:`FetchSession`, so CI never
calls DBnomics live (tests replay canned bodies).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

from schelling.evidence.claim import EvidenceClaim
from schelling.evidence.http import FetchSession

_API = "https://api.db.nomics.world/v22"
_SITE = "https://db.nomics.world"


@dataclass(frozen=True)
class DatasetHit:
    """A dataset matching a search — the middle step between a query and a series."""

    provider_code: str
    dataset_code: str
    name: str
    nb_series: int
    url: str


@dataclass(frozen=True)
class SeriesHit:
    """A series inside a dataset — enough to fetch its observations."""

    provider_code: str
    dataset_code: str
    series_code: str
    name: str
    url: str


def dbnomics_search(session: FetchSession, query: str, *, limit: int = 10) -> list[DatasetHit]:
    """Search DBnomics for datasets matching ``query`` (step 1: which dataset holds the number)."""
    params = urlencode({"q": query, "limit": str(limit)})
    data = session.fetch_json(f"{_API}/search?{params}")
    docs = ((data or {}).get("results") or {}).get("docs") or []
    hits: list[DatasetHit] = []
    for d in docs:
        provider = str(d.get("provider_code", ""))
        dataset = str(d.get("code", ""))
        if not provider or not dataset:
            continue
        hits.append(
            DatasetHit(
                provider_code=provider,
                dataset_code=dataset,
                name=str(d.get("name", "")),
                nb_series=int(d.get("nb_series", 0) or 0),
                url=f"{_SITE}/{provider}/{dataset}",
            )
        )
    return hits


def dbnomics_series_in_dataset(
    session: FetchSession, provider: str, dataset: str, *, query: str = "", limit: int = 20
) -> list[SeriesHit]:
    """List series in a dataset, optionally narrowed by ``query`` (step 2: which series)."""
    params: dict[str, str] = {"limit": str(limit)}
    if query:
        params["q"] = query
    url = f"{_API}/series/{quote(provider)}/{quote(dataset, safe=':')}?{urlencode(params)}"
    data = session.fetch_json(url)
    docs = ((data or {}).get("series") or {}).get("docs") or []
    out: list[SeriesHit] = []
    for s in docs:
        code = str(s.get("series_code", ""))
        if not code:
            continue
        out.append(
            SeriesHit(
                provider_code=str(s.get("provider_code", provider)),
                dataset_code=str(s.get("dataset_code", dataset)),
                series_code=code,
                name=str(s.get("series_name", "")),
                url=f"{_SITE}/{provider}/{dataset}/{code}",
            )
        )
    return out


def _latest_observation(periods: list[Any], values: list[Any]) -> tuple[str, float] | None:
    """The last non-null (period, value) pair — DBnomics stores parallel period/value arrays."""
    for period, value in zip(reversed(periods), reversed(values), strict=False):
        if isinstance(value, int | float):
            return str(period), float(value)
    return None


def _trailing_unit(series_name: str) -> str:
    """Pull a trailing unit from a DBnomics series name (best-effort; empty when absent).

    DBnomics names put the unit last after a dash separator; the en/em-dash forms below match the
    real data, so they are deliberate non-ASCII literals.
    """
    for sep in (" – ", " — ", " - "):  # noqa: RUF001 — en/em-dash match real DBnomics names
        if sep in series_name:
            return series_name.rsplit(sep, 1)[1].strip()
    return ""


def dbnomics_series(
    session: FetchSession, provider: str, dataset: str, series: str
) -> EvidenceClaim:
    """Fetch a series' latest observation as a citable claim (step 3: the number itself).

    ``series`` may be a full series code or a DBnomics dimension mask; the first matching series is
    used. Raises ``ValueError`` if nothing matches or the series has no numeric observation.
    """
    url = (
        f"{_API}/series/{quote(provider)}/{quote(dataset, safe=':')}/{quote(series)}?observations=1"
    )
    data = session.fetch_json(url)
    docs = ((data or {}).get("series") or {}).get("docs") or []
    if not docs:
        raise ValueError(f"DBnomics: no series matched {provider}/{dataset}/{series}")
    doc = docs[0]
    obs = _latest_observation(doc.get("period", []) or [], doc.get("value", []) or [])
    if obs is None:
        raise ValueError(
            f"DBnomics: series {provider}/{dataset}/{series} has no numeric observation"
        )
    period, value = obs
    code = str(doc.get("series_code", series))
    name = str(doc.get("series_name", ""))
    dataset_name = str(doc.get("dataset_name", dataset))
    freq = str(doc.get("@frequency", "")).strip()
    note = dataset_name + (f" · {freq}" if freq else "")
    return EvidenceClaim(
        provider="dbnomics",
        identifier=f"{provider}/{dataset}/{code}",
        title=name or code,
        retrieved_at=session.today,
        value=value,
        unit=_trailing_unit(name),
        period=period,
        url=f"{_SITE}/{provider}/{dataset}/{code}",
        note=note,
    )
