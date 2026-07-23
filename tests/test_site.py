"""The static site (Session 31, D31): generation determinism, the drift check, no hand-typed
figures, offline-cleanliness, and the honesty rules."""

from __future__ import annotations

import re
from pathlib import Path

from schelling.site.data import LedgerRow, QuestionInfo, ReportLink, SiteData, gather
from schelling.site.render import build_site, check_site, write_site

REPO_ROOT = Path(__file__).resolve().parent.parent

# Numbers that are structural HTML/spec tokens, not figures: viewport initial-scale=1, the "8" of
# UTF-8, and the "256" of SHA-256. Everything else in a page must trace to an artifact.
_STRUCTURAL = {"1", "8", "256"}
_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?")
_SCRIPT = re.compile(r"<script>.*?</script>", re.DOTALL)
_ENTITY = re.compile(r"&#?\w+;")  # HTML entities (e.g. &#39;, &amp;) are not figures


def _sample_data() -> SiteData:
    """A fully-populated SiteData with realistic values — hermetic, no git/pytest subprocess."""
    ledger = [
        LedgerRow(
            "challenge",
            "v1",
            "Q-2026-USIRAN-STAGE2",
            "2026-07-21",
            "34.576",
            "aece91bdcfd8a35aeea15c98fc6d10af11793fce5a637f9e277f1225a1d1e54f",
        ),
        LedgerRow(
            "compromise",
            "v1",
            "Q-2026-IAEA-SEP",
            "2026-07-22",
            "50.518",
            "e8d10117192f1259b9e9ab6250641f82e0c1d50a4c00c2e73ff193580f867f99",
        ),
    ]

    def ev(value: str) -> dict[str, str]:
        return {"value": value, "source": "BACKTEST.md", "prov": "578beb2"}

    return SiteData(
        decisions_count=152,
        test_count="430",
        resolution_date="2026-08-31",
        grading_date="2026-09-01",
        ledger=ledger,
        graded_questions=frozenset(),
        evidence={
            "E-DEU-N": ev("351"),
            "E-REPL-MEDIAN": ev("9.530"),
            "E-METHOD-challenge_rp": ev("26.83 / 38.51"),
            "E-METHOD-baseline_wmean": ev("22.99 / 29.77"),
            "E-METHOD-baseline_median": ev("28.37 / 40.64"),
            "E-ORACLE-MAE": ev("23.84 vs 22.99"),
            "E-ORACLE-GAP": ev("-0.84"),
            "E-TESTS": ev("430"),
        },
        gate_verdict="FAILED",
        successor_verdict="No candidate beats the compromise weighted mean on TEST.",
        leaderboard_header=[
            "Candidate",
            "Scored on",
            "dev MAE",
            "TEST MAE",
            "comp. MAE",
            "Δ (95% CI)",
            "beats?",
        ],
        leaderboard_rows=[
            [
                "Candidate A — status-quo gravity",
                "TEST rp-issues",
                "24.96 (23.87)",
                "22.09",
                "21.26",
                "+0.83 [-0.15, +1.91]",
                "no",
            ],
            [
                "Candidate B — regime-aware settlement",
                "TEST (all)",
                "24.86 (24.10)",
                "21.57",
                "21.09",
                "+0.48 [-0.69, +1.76]",
                "no",
            ],
        ],
        abstract="An open replication reproduces the case (9.530) and fails on 351 issues.",
        bibliography=[
            "Bueno de Mesquita, B. (2011). A New Model. CMPS 28(1): 65-87.",
            "Achen, C.H. (2006). Evaluating models. In The European Union Decides.",
        ],
        reports=[ReportLink("Q-2026-IAEA-SEP.report.html", "Q-2026-IAEA-SEP")],
        questions={
            "Q-2026-USIRAN-STAGE2": QuestionInfo(
                "Q-2026-USIRAN-STAGE2", "GRADING-Q-2026-USIRAN-STAGE2.md", "2026-08-31"
            ),
            "Q-2026-IAEA-SEP": QuestionInfo(
                "Q-2026-IAEA-SEP", "GRADING-Q-2026-IAEA-SEP.md", "2026-09-30"
            ),
        },
    )


def _pages(data: SiteData) -> dict[str, str]:
    return {k: v for k, v in build_site(REPO_ROOT, data=data).items() if k.endswith(".html")}


# --------------------------------------------------------------------------- determinism (D31.6)
def test_generation_is_deterministic() -> None:
    data = _sample_data()
    assert build_site(REPO_ROOT, data=data) == build_site(REPO_ROOT, data=data)


def test_build_writes_the_expected_fileset() -> None:
    files = build_site(REPO_ROOT, data=_sample_data())
    assert set(files) == {
        "index.html",
        "ledger.html",
        "findings.html",
        "paper.html",
        "reports/index.html",
        "site.css",
        ".nojekyll",
    }


# --------------------------------------------------------------------------- drift check (D31.2)
def test_check_reports_no_drift_after_write(tmp_path: Path) -> None:
    data = _sample_data()
    # write the sample site (from fixed data, not a re-gather), then diff a fresh build against it
    files = build_site(REPO_ROOT, data=data)
    for rel, content in files.items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    drift = [
        rel
        for rel, c in build_site(REPO_ROOT, data=data).items()
        if (tmp_path / rel).read_text() != c
    ]
    assert drift == []


def test_check_detects_a_mutated_page(tmp_path: Path) -> None:
    data = _sample_data()
    files = build_site(REPO_ROOT, data=data)
    for rel, content in files.items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    (tmp_path / "index.html").write_text("<html>tampered</html>")
    drift = [rel for rel, content in files.items() if (tmp_path / rel).read_text() != content]
    assert drift == ["index.html"]


def test_check_site_helper_flags_missing_files(tmp_path: Path) -> None:
    # nothing written yet → every file is drift
    drift = check_site(REPO_ROOT, tmp_path, repo_url="https://example.test/r")
    assert "index.html" in drift and "site.css" in drift


def test_write_site_creates_files_on_disk(tmp_path: Path) -> None:
    written = write_site(REPO_ROOT, tmp_path)
    assert "reports/index.html" in written
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "reports" / "index.html").exists()
    assert (tmp_path / "site.css").read_text().startswith(":root")


# --------------------------------------------------------------------------- no hand-typed figures
def test_no_hand_typed_figures() -> None:
    """Every number printed in the HTML traces to an artifact figure (D31.6)."""
    data = _sample_data()
    allowed = data.provenance() | _STRUCTURAL
    for name, page in _pages(data).items():
        # the countdown script's arithmetic constants and HTML entities are not figures
        scrubbed = _ENTITY.sub(" ", _SCRIPT.sub("", page))
        for token in _NUM.findall(scrubbed):
            assert token in allowed, f"{name}: un-sourced number {token!r}"


# --------------------------------------------------------------------------- offline-cleanliness
def test_pages_load_no_external_resources() -> None:
    """No page pulls an embedded resource off-site: no external src=, no external stylesheet, no
    @import, no url(http…). Navigational <a href> links to the repo are fine (D31.6)."""
    for name, page in _pages(_sample_data()).items():
        assert "@import" not in page, name
        assert not re.search(r'src\s*=\s*"https?:', page), name
        assert not re.search(r"url\(\s*https?:", page), name
        for link in re.findall(r"<link[^>]*>", page):
            href = re.search(r'href\s*=\s*"([^"]*)"', link)
            assert href is not None and not href.group(1).startswith("http"), f"{name}: {link}"
        # the only stylesheet is the shared, relative site.css
        assert re.search(r'<link rel="stylesheet" href="(?:\.\./)?site\.css">', page), name


def test_committed_reports_are_offline_clean() -> None:
    """Reports copied into docs/reports/ embed no external resource either (they may cite sources
    via navigational <a href> links, which is fine)."""
    reports_dir = REPO_ROOT / "docs" / "reports"
    for path in sorted(reports_dir.glob("*.html")):
        page = path.read_text()
        assert not re.search(r'src\s*=\s*"https?:', page), path.name
        assert "@import" not in page, path.name
        assert not re.search(r'<link[^>]*rel="stylesheet"[^>]*href="https?:', page), path.name


# --------------------------------------------------------------------------- honesty rules (D31.5)
def test_honesty_shows_graded_beside_sealed() -> None:
    """The graded count is always rendered beside the sealed count — as adjacent stat cards on both
    the index and the ledger page (D31.5, restyled D33.3)."""
    data = _sample_data()  # sealed_count == 2, graded_count == 0
    sealed_card = '<div class="stat"><p class="k">Forecasts sealed</p><p class="v">2</p></div>'
    graded_card = '<div class="stat"><p class="k">Graded</p><p class="v">0</p></div>'
    for name in ("index.html", "ledger.html"):
        page = build_site(REPO_ROOT, data=data)[name]
        assert sealed_card in page, name
        assert graded_card in page, name
        # the two cards are adjacent (sealed immediately followed by graded)
        assert sealed_card + graded_card in page, name


def test_no_accuracy_claim_while_ungraded() -> None:
    data = _sample_data()  # graded_count == 0
    assert data.graded_count == 0
    for name, page in _pages(data).items():
        low = page.lower()
        # the guard: never assert forecast accuracy while nothing is graded
        assert "our forecasts were accurate" not in low, name
        assert "forecast accuracy of" not in low, name
        assert "% accurate" not in low, name


def test_graded_count_reflects_recorded_outcomes() -> None:
    data = _sample_data()
    graded = SiteData(
        ledger=data.ledger,
        graded_questions=frozenset({"Q-2026-IAEA-SEP"}),
    )
    assert graded.sealed_count == 2
    assert graded.graded_count == 1


# --------------------------------------------------------------------------- reference design (D33)
def test_reference_design_structure_holds() -> None:
    """The specifics that must not drift from the approved reference (D33.4): a two-line h1 whose
    second line carries the accent; no HTML tables anywhere (hashes never live in a table cell); the
    full 64-char SHA-256 on its own monospace .hash line; the nav with brand + navlinks."""
    data = _sample_data()
    for name, page in _pages(data).items():
        assert "<h1>" in page and '<span class="turn">' in page, name  # two-line accented h1
        assert "<table" not in page and "</td>" not in page, name  # never a table
        assert '<nav><div class="wrap"><a class="brand"' in page, name
    # every ledger row: the full 64-char hash on its own monospace line, never in a table cell
    for name in ("index.html", "ledger.html"):
        page = build_site(REPO_ROOT, data=data)[name]
        hashes = re.findall(r'<p class="hash">([0-9a-f]{64})</p>', page)
        assert len(hashes) == data.sealed_count, name
    # findings gate numbers all trace and render as "n / n" or a single sourced figure
    findings = _pages(data)["findings.html"]
    assert 'class="gate"' in findings and 'class="gates"' in findings


# --------------------------------------------------------------------------- real-repo integration
def test_gather_parses_the_real_repository() -> None:
    """gather() reads the committed artifacts and returns sane, sourced values."""
    data = gather(REPO_ROOT)
    assert data.sealed_count >= 6  # the sealed ledger rows
    assert data.grading_date and re.match(r"\d{4}-\d{2}-\d{2}", data.grading_date)
    assert data.gate_verdict == "FAILED"
    assert data.fig("E-DEU-N") == "351"
    assert data.decisions_count > 100
    # the real site regenerates and is in sync with what is committed under docs/
    assert check_site(REPO_ROOT, REPO_ROOT / "docs") == []
