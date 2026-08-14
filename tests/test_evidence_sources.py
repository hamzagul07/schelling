"""Structured evidence sources (Session 52, D52): DBnomics, UCDP, ACLED, archives, and the item-0
fixes (friendly HTTP errors, Metaculus token, GDELT 429). Replay fixtures only — CI never calls a
live API (CLAUDE.md rule 2).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest
from typer.testing import CliRunner

from schelling.evidence.acled import acled_reference_class
from schelling.evidence.archives import archive_enumerate
from schelling.evidence.claim import EvidenceClaim, widen_range
from schelling.evidence.dbnomics import (
    dbnomics_search,
    dbnomics_series,
    dbnomics_series_in_dataset,
)
from schelling.evidence.gdelt import _gdelt_fetch
from schelling.evidence.http import (
    Budget,
    Fetcher,
    FetchError,
    FetchSession,
    ReplayFetcher,
    UrllibFetcher,
)
from schelling.evidence.metaculus import _auth_headers
from schelling.evidence.providers import REGISTRY, availability_report
from schelling.evidence.ucdp import ucdp_reference_class

runner = CliRunner()


def _session(responses: dict[str, str], *, budget: int = 10) -> FetchSession:
    return FetchSession(
        ReplayFetcher(responses=responses), today="2026-08-14", budget=Budget(budget)
    )


def _game_json(tmp_path: Path) -> Path:
    """A minimal on-disk GameSpec so CLI tests need no gitignored analyses/ fixture."""
    from schelling.schemas.question import Continuum, GameSpec
    from schelling.schemas.stakeholders import Actor, TriangularEstimate

    game = GameSpec(
        question_id="Q-DEMO",
        frozen_at="2026-08-14",
        continuum=Continuum(label="l", anchor_0="0", anchor_100="100"),
        actors=[
            Actor(
                id="a",
                name="A",
                position=TriangularEstimate.point(50.0),
                salience=TriangularEstimate.point(50.0),
                capability=TriangularEstimate.point(50.0),
                evidence=[],
            )
        ],
        template="t",
        horizon="h",
    )
    path = tmp_path / "game.json"
    path.write_text(game.model_dump_json())
    return path


def _no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("UCDP_ACCESS_TOKEN", "ACLED_API_KEY", "ACLED_EMAIL", "METACULUS_TOKEN"):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------- item 0: friendly HTTP errors
def test_fetcherror_carries_status_and_url() -> None:
    exc = FetchError("nope", status=403, url="https://x")
    assert exc.status == 403 and exc.url == "https://x"


def test_urllib_fetcher_maps_http_error_to_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401/403/429 becomes a FetchError carrying the status, so the CLI can say which."""

    def _raise(*_a: object, **_k: object) -> object:
        raise urllib.error.HTTPError("https://api.example/x", 429, "Too Many Requests", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    with pytest.raises(FetchError) as ei:
        UrllibFetcher().fetch("https://api.example/x")
    assert ei.value.status == 429 and "429" in str(ei.value)


def test_metaculus_auth_headers_present_only_with_token() -> None:
    assert _auth_headers("TK") == {"Authorization": "Token TK"}
    assert _auth_headers("") is None
    assert _auth_headers("   ") is None


class _Flaky:
    """Raises the given statuses in turn, then serves ``ok`` — for the 429 retry test."""

    def __init__(self, statuses: list[int], ok: str) -> None:
        self.statuses = statuses
        self.ok = ok
        self.calls = 0

    def fetch(
        self, url: str, *, method: str = "GET", body: object = None, headers: object = None
    ) -> str:
        if self.calls < len(self.statuses):
            code = self.statuses[self.calls]
            self.calls += 1
            raise FetchError(f"HTTP {code}", status=code, url=url)
        self.calls += 1
        return self.ok


def test_gdelt_retries_once_on_429_then_succeeds() -> None:
    fetcher: Fetcher = _Flaky([429], '{"articles": []}')
    sess = FetchSession(fetcher, today="2026-08-14", budget=Budget(5))
    data = _gdelt_fetch(sess, "https://api.gdeltproject.org/x", sleep=0.0)
    assert data == {"articles": []}


def test_gdelt_second_429_is_a_clear_message_not_a_traceback() -> None:
    fetcher: Fetcher = _Flaky([429, 429], '{"articles": []}')
    sess = FetchSession(fetcher, today="2026-08-14", budget=Budget(5))
    with pytest.raises(FetchError) as ei:
        _gdelt_fetch(sess, "https://api.gdeltproject.org/x", sleep=0.0)
    assert ei.value.status == 429 and "rate-limited" in str(ei.value)


# ---------------------------------------------------------------- item 1: DBnomics
_DBN_SEARCH = (
    '{"results":{"docs":[{"code":"WEO:2025-04","provider_code":"IMF",'
    '"name":"World Economic Outlook","nb_series":100}]}}'
)


def _dbn_series(code: str, name: str, values: list[float]) -> str:
    periods = ",".join(f'"{2028 + i}"' for i in range(len(values)))
    vals = ",".join(str(v) for v in values)
    return (
        '{"series":{"docs":[{'
        f'"series_code":"{code}","series_name":"{name}","provider_code":"IMF",'
        f'"dataset_code":"WEO:2025-04","dataset_name":"WEO","@frequency":"annual",'
        f'"period":[{periods}],"value":[{vals}]'
        "}]}}"
    )


def test_dbnomics_search_parses_datasets() -> None:
    sess = _session({"https://api.db.nomics.world/v22/search": _DBN_SEARCH})
    hits = dbnomics_search(sess, "world economic outlook")
    assert len(hits) == 1
    assert hits[0].provider_code == "IMF" and hits[0].dataset_code == "WEO:2025-04"
    assert hits[0].nb_series == 100


def test_dbnomics_series_takes_the_latest_numeric_observation() -> None:
    body = _dbn_series(
        "SAU.NGDPD.us_dollars", "Saudi Arabia - GDP - U.S. dollars", [1200.0, 1300.0, 1374.158]
    )
    sess = _session({"https://api.db.nomics.world/v22/series/IMF/WEO:latest/SAU": body})
    claim = dbnomics_series(sess, "IMF", "WEO:latest", "SAU.NGDPD")
    assert claim.provider == "dbnomics"
    assert claim.value == 1374.158 and claim.period == "2030"
    assert claim.unit == "U.S. dollars"
    assert claim.identifier == "IMF/WEO:latest/SAU.NGDPD.us_dollars"
    assert claim.retrieved_at == "2026-08-14"  # supplied, never a wall clock


def test_dbnomics_series_no_match_raises() -> None:
    sess = _session({"https://api.db.nomics.world/v22/series": '{"series":{"docs":[]}}'})
    with pytest.raises(ValueError, match="no series matched"):
        dbnomics_series(sess, "IMF", "WEO:latest", "NOPE")


_DBN_IN_DATASET = (
    '{"series":{"docs":['
    '{"series_code":"SAU.NGDPD.us_dollars","series_name":"Saudi - GDP - USD",'
    '"provider_code":"IMF","dataset_code":"WEO:2025-04"},'
    '{"series_code":"IRN.NGDPD.us_dollars","series_name":"Iran - GDP - USD",'
    '"provider_code":"IMF","dataset_code":"WEO:2025-04"}]}}'
)


def test_dbnomics_series_in_dataset_lists_series() -> None:
    # keyed with the trailing '?' so it matches only the list call, not a /CODE series fetch
    sess = _session({"https://api.db.nomics.world/v22/series/IMF/WEO:latest?": _DBN_IN_DATASET})
    hits = dbnomics_series_in_dataset(sess, "IMF", "WEO:latest")
    assert len(hits) == 2
    assert hits[0].series_code == "SAU.NGDPD.us_dollars" and hits[0].provider_code == "IMF"


# ---------------------------------------------------------------- item 4: claim + widening
def test_evidence_claim_citation_carries_provenance() -> None:
    c = EvidenceClaim(
        provider="dbnomics",
        identifier="IMF/WEO/SAU.NGDPD",
        title="GDP",
        retrieved_at="2026-08-14",
        value=1374.16,
        unit="USD",
        period="2030",
    )
    cit = c.citation()
    assert (
        "dbnomics:IMF/WEO/SAU.NGDPD" in cit and "1374.16" in cit and "retrieved 2026-08-14" in cit
    )


def test_widen_range_is_the_union_never_a_resolution() -> None:
    a = EvidenceClaim(provider="p", identifier="a", title="a", retrieved_at="d", value=490.0)
    b = EvidenceClaim(provider="p", identifier="b", title="b", retrieved_at="d", value=1374.0)
    w = widen_range([a, b])
    assert w is not None
    assert w.lo == 490.0 and w.hi == 1374.0  # union, not an average
    assert len(w.claims) == 2 and "WIDENED" in w.as_note()


def test_widen_range_none_when_no_numeric_claims() -> None:
    rec = EvidenceClaim(
        provider="p", identifier="a", title="a record", retrieved_at="d", value=None
    )
    assert widen_range([rec]) is None


# ---------------------------------------------------------------- item 2: UCDP + ACLED
_UCDP = (
    '{"TotalCount":42,"Result":['
    '{"id":1,"best":25,"country":"Iran","date_start":"2024-03-01","conflict_name":"X"},'
    '{"id":2,"best":5,"country":"Iran","date_start":"2024-04-01","conflict_name":"Y"}]}'
)
_ACLED = (
    '{"count":30,"data":['
    '{"data_id":100,"fatalities":3,"country":"Iran","event_type":"Protests","event_date":"2024-05-01","source":"Reuters"},'
    '{"data_id":101,"fatalities":0,"country":"Iran","event_type":"Riots","event_date":"2024-05-02","source":"AP"}]}'
)


def test_ucdp_requires_a_portal_token() -> None:
    sess = _session({})
    with pytest.raises(ValueError, match="access token"):
        ucdp_reference_class(sess, token="", country="645")


def test_ucdp_reference_class_summarises_and_enumerates() -> None:
    sess = _session({"https://ucdpapi.pcr.uu.se/api/gedevents/24.1": _UCDP})
    rc = ucdp_reference_class(sess, token="TK", country="645", start_date="2024-01-01")
    assert rc.total_count == 42  # the base-rate denominator
    assert rc.total_fatalities == 30
    assert rc.summary.value == 42.0 and rc.summary.provider == "ucdp"
    assert len(rc.events) == 2 and rc.events[0].value == 25.0


def test_acled_requires_key_and_email() -> None:
    sess = _session({})
    with pytest.raises(ValueError, match="API key"):
        acled_reference_class(sess, key="", email="", country="Iran")


def test_acled_reference_class_summarises_and_hides_the_key() -> None:
    sess = _session({"https://api.acleddata.com/acled/read": _ACLED})
    rc = acled_reference_class(sess, key="SECRET", email="me@x", country="Iran")
    assert rc.count == 30 and rc.total_fatalities == 3
    assert "SECRET" not in rc.summary.identifier and "me@x" not in rc.summary.identifier
    assert len(rc.events) == 2 and rc.events[0].value == 3.0


def test_providers_report_availability_from_the_environment() -> None:
    report = dict((info.name, avail) for info, avail in availability_report({}))
    assert report["dbnomics"].available and report["archive"].available
    assert not report["ucdp"].available and "UCDP_ACCESS_TOKEN" in report["ucdp"].reason
    assert not report["acled"].available and "ACLED_API_KEY" in report["acled"].reason
    # with the token set, UCDP flips to available
    ok = REGISTRY["ucdp"].availability({"UCDP_ACCESS_TOKEN": "tk"})
    assert ok.available and ok.reason == ""


# ---------------------------------------------------------------- item 3: archives
_RSS = (
    '<?xml version="1.0"?><rss version="2.0"><channel><title>IAEA</title>'
    "<item><title>Board of Governors statement</title>"
    "<link>https://iaea.org/a</link><pubDate>26-08-12  12:44</pubDate></item>"
    "<item><title>Older release</title>"
    "<link>https://iaea.org/b</link><pubDate>Wed, 01 Jul 2026 09:00:00 GMT</pubDate></item>"
    "<item><title>Undated note</title><link>https://iaea.org/c</link><pubDate></pubDate></item>"
    "</channel></rss>"
)
_ATOM = (
    '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>F</title>'
    '<entry><title>Session A</title><link href="https://x/a"/><updated>2026-08-05T00:00:00Z</updated></entry>'
    "</feed>"
)


def test_archive_parses_rss_and_normalizes_the_iaea_date() -> None:
    sess = _session({"https://www.iaea.org/feeds/topnews": _RSS})
    claims = archive_enumerate(sess, "iaea")
    assert len(claims) == 3
    first = claims[0]
    assert first.period == "2026-08-12" and first.provider == "iaea-archive"  # IAEA YY-MM-DD parsed
    assert first.value is None and first.url == "https://iaea.org/a"
    assert claims[1].period == "2026-07-01"  # RFC-822 parsed


def test_archive_atom_feed_via_url_override() -> None:
    sess = _session({"https://example/atom": _ATOM})
    claims = archive_enumerate(sess, "custom", url="https://example/atom")
    assert len(claims) == 1 and claims[0].period == "2026-08-05"
    assert claims[0].url == "https://x/a"


def test_archive_date_window_filters_but_keeps_undated() -> None:
    sess = _session({"https://www.iaea.org/feeds/topnews": _RSS})
    claims = archive_enumerate(sess, "iaea", since="2026-08-01", until="2026-08-31")
    periods = [c.period for c in claims]
    assert "2026-08-12" in periods  # in window
    assert "2026-07-01" not in periods  # out of window, dropped
    assert "" in periods  # undated entry kept — a human decides
    undated = next(c for c in claims if not c.period)
    assert "date unparsed" in undated.note


def test_archive_unknown_body_raises() -> None:
    sess = _session({})
    with pytest.raises(ValueError, match="unknown archive body"):
        archive_enumerate(sess, "nope")


# ---------------------------------------------------------------- item 5: the one CLI interface
def _patch_session(monkeypatch: pytest.MonkeyPatch, responses: dict[str, str]) -> None:
    from schelling import cli

    monkeypatch.setattr(cli, "_live_session", lambda b, c=0.0: _session(responses, budget=b))


def test_cli_evidence_providers_lists_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    from schelling.cli import app

    _no_keys(monkeypatch)
    res = runner.invoke(app, ["evidence", "providers"])
    assert res.exit_code == 0
    assert "dbnomics" in res.stdout and "UNAVAILABLE" in res.stdout and "ucdp" in res.stdout


def test_cli_evidence_dbnomics_series_prints_a_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    from schelling.cli import app

    body = _dbn_series(
        "SAU.NGDPD.us_dollars", "Saudi Arabia - GDP - U.S. dollars", [1300.0, 1374.158]
    )
    _patch_session(monkeypatch, {"https://api.db.nomics.world/v22/series/IMF/WEO:latest/SAU": body})
    res = runner.invoke(app, ["evidence", "dbnomics", "--series", "IMF/WEO:latest/SAU.NGDPD"])
    assert res.exit_code == 0
    assert "dbnomics:IMF" in res.stdout and "1374.16" in res.stdout


def test_cli_evidence_dbnomics_in_dataset_lists_series(monkeypatch: pytest.MonkeyPatch) -> None:
    from schelling.cli import app

    _patch_session(
        monkeypatch, {"https://api.db.nomics.world/v22/series/IMF/WEO:latest?": _DBN_IN_DATASET}
    )
    res = runner.invoke(app, ["evidence", "dbnomics", "--in", "IMF/WEO:latest"])
    assert res.exit_code == 0
    assert "SAU.NGDPD.us_dollars" in res.stdout and "IRN.NGDPD.us_dollars" in res.stdout


def test_cli_evidence_dbnomics_two_series_shows_widened_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from schelling.cli import app

    sau = _dbn_series("SAU.NGDPD.us_dollars", "Saudi - GDP - USD", [1374.0])
    irn = _dbn_series("IRN.NGDPD.us_dollars", "Iran - GDP - USD", [490.0])
    _patch_session(
        monkeypatch,
        {
            "https://api.db.nomics.world/v22/series/IMF/WEO:latest/SAU": sau,
            "https://api.db.nomics.world/v22/series/IMF/WEO:latest/IRN": irn,
        },
    )
    res = runner.invoke(
        app,
        [
            "evidence",
            "dbnomics",
            "--series",
            "IMF/WEO:latest/SAU.NGDPD",
            "--series",
            "IMF/WEO:latest/IRN.NGDPD",
        ],
    )
    assert res.exit_code == 0
    assert "Widened range" in res.stdout and "not resolved to one side" in res.stdout


def test_cli_evidence_archive_enumerates_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    from schelling.cli import app

    _patch_session(monkeypatch, {"https://www.iaea.org/feeds/topnews": _RSS})
    res = runner.invoke(app, ["evidence", "archive", "iaea"])
    assert res.exit_code == 0
    assert "candidate record" in res.stdout and "a human ratifies" in res.stdout


def test_cli_evidence_ucdp_without_token_is_friendly_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from schelling.cli import app

    _no_keys(monkeypatch)
    res = runner.invoke(app, ["evidence", "ucdp", "--country", "645"])
    assert res.exit_code == 1
    assert "unavailable" in res.stderr and "UCDP_ACCESS_TOKEN" in res.stderr
    assert isinstance(res.exception, SystemExit)  # a clean exit, not an unhandled traceback
    assert "Traceback" not in (res.stdout + res.stderr)


def test_cli_crowd_403_reports_unavailable_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The item-0 headline: a Metaculus 403 now prints one friendly line, never a stack trace."""
    from schelling import cli
    from schelling.cli import app

    class _Forbidden:
        def fetch(
            self, url: str, *, method: str = "GET", body: object = None, headers: object = None
        ) -> str:
            raise FetchError(f"HTTP 403 for {url}", status=403, url=url)

    _no_keys(monkeypatch)
    monkeypatch.setattr(
        cli,
        "_live_session",
        lambda b, c=0.0: FetchSession(_Forbidden(), today="2026-08-14", budget=Budget(b)),
    )
    res = runner.invoke(app, ["crowd", str(_game_json(tmp_path)), "--search", "IAEA"])
    # exit non-zero, a friendly line on stderr, and NO traceback (the pre-Session-52 behaviour was
    # an unhandled FetchError dumping a stack trace)
    assert res.exit_code == 1
    assert "unavailable" in res.stderr
    assert isinstance(res.exception, SystemExit)
    assert "Traceback" not in (res.stdout + res.stderr)
