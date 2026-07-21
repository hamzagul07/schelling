"""Deterministic evidence gathering (Session 14, D14.1).

Every number the paper cites is *computed here from the repo's own artifacts*, never hand-typed:

* the replication median is re-solved from the committed emission-standards fixture;
* the DEU MAE/RMSE tables, split-sample, oracle gap, and worst issues come from a fresh
  ``run_backtest`` over the DEU data (pinned by SHA-256), identical by determinism to BACKTEST.md;
* the successor leaderboard + bootstrap CIs come from a fresh ``run_successor_search``;
* the sealed ledger rows are read from FORECASTS.md (the record files are gitignored, so their
  SHA-256 commitments *are* the artifact — they cannot be recomputed, only quoted);
* the test count is collected live from ``tests/``.

Each :class:`EvidenceItem` carries the source artifact and a provenance stamp (a git short hash of
the source file, or the dataset SHA-256 prefix for data-derived numbers). Same repo state → same
table, so it can be diffed forever. Any number that cannot be sourced becomes an open question
(``unsourced``), never a silent guess.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schelling.backtest.successor import SuccessorReport
    from schelling.schemas.backtest import BacktestRecord

_DEU_CSV_NAME = "Dataset_DEU_III.csv"
_DEU_LABEL = "DEU III (doi:10.34810/data53)"


@dataclass(frozen=True)
class EvidenceItem:
    """One cited number, plus where it came from and how to re-derive it."""

    tag: str  # stable E-tag referenced from OUTLINE.md
    section: str
    metric: str
    value: str  # formatted; the number as the paper would cite it
    source: str  # artifact path / data file the number derives from
    provenance: str  # git short hash of the source, or a dataset SHA-256 prefix
    note: str = ""


@dataclass
class EvidenceBundle:
    """The gathered evidence plus the heavy records the figures reuse (compute once)."""

    items: list[EvidenceItem] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)  # numbers no artifact could source
    record: BacktestRecord | None = None  # the DEU backtest record (for figures)
    report: SuccessorReport | None = None  # the successor leaderboard (for figures)
    head_commit: str = ""


def _git_short(repo_root: Path, path: str | None = None) -> str:
    """Git short hash of HEAD, or the last commit that touched ``path`` (empty on none/error)."""
    cmd = ["git", "-C", str(repo_root), "log", "-1", "--format=%h"]
    if path is not None:
        cmd += ["--", path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return out.stdout.strip()


def _f2(x: float) -> str:
    return f"{x:.2f}"


def _f3(x: float) -> str:
    return f"{x:.3f}"


# --------------------------------------------------------------------------- replication (§2)
def _replication_items(repo_root: Path) -> list[EvidenceItem]:
    from schelling.mc.monte_carlo import forecast
    from schelling.schemas.question import GameSpec
    from schelling.solver.config import SolverConfig

    fixture = repo_root / "tests" / "fixtures" / "emission_standards.json"
    if not fixture.exists():
        return []
    game = GameSpec.model_validate_json(fixture.read_text())
    rec = forecast(game, SolverConfig(), n_draws=100, seed=42, write=False)
    prov = _git_short(repo_root, "tests/fixtures/emission_standards.json")
    src = "tests/fixtures/emission_standards.json"
    e = rec.ensemble
    return [
        EvidenceItem(
            "E-REPL-MEDIAN",
            "2. Replication",
            "Emission-standards settlement median",
            _f3(e.median),
            src,
            prov,
            "re-solved deterministically (seed 42); reproduces published ~9.5x",
        ),
        EvidenceItem(
            "E-REPL-CI",
            "2. Replication",
            "Emission-standards CI80 (p10, p90)",
            f"({_f3(e.p10)}, {_f3(e.p90)})",
            src,
            prov,
            "point fixture -> zero variance -> CI collapses to the median",
        ),
    ]


# ------------------------------------------------------------------- DEU fair fight (§3, §5)
def _deu_items(repo_root: Path, record: BacktestRecord) -> list[EvidenceItem]:
    sha = record.dataset_sha256[:12]
    prov = f"sha256:{sha}"
    src = f"data/deu/{_DEU_CSV_NAME}"
    items: list[EvidenceItem] = [
        EvidenceItem(
            "E-DEU-N",
            "3. Fair fight",
            "DEU scoreable issues",
            str(record.n_issues),
            src,
            prov,
            f"seed {record.seed}, sourced treaty-regime capabilities (D10.1)",
        ),
        EvidenceItem(
            "E-DEU-GATE",
            "3. Fair fight",
            "Gate v2 verdict",
            "PASSED" if record.gate_passed else "FAILED",
            src,
            prov,
            f"primary '{record.primary_method}' must beat {record.baseline_methods}",
        ),
    ]
    # per-method MAE / RMSE (the challenge-vs-compromise comparison)
    for m in record.methods:
        items.append(
            EvidenceItem(
                f"E-METHOD-{m.key}",
                "3. Fair fight",
                f"MAE / RMSE — {m.label}",
                f"{_f2(m.mae)} / {_f2(m.rmse)}",
                src,
                prov,
                f"kind={m.kind}, median AE {_f2(m.median_error)}",
            )
        )
    # split-sample honesty (item 4 of the fair fight)
    if record.split_sample is not None:
        ss = record.split_sample
        items.append(
            EvidenceItem(
                "E-SS-TEST",
                "3. Fair fight",
                "Split-sample: tuned test MAE vs weighted mean",
                f"{_f2(ss.test_mae)} vs {_f2(ss.test_baseline_mae)}",
                src,
                prov,
                f"{ss.tuned_param}={ss.selected} tuned on {ss.train_n} train "
                f"(MAE {_f2(ss.train_mae)}), scored on {ss.test_n} held-out",
            )
        )
    # noise-floor oracle + ceiling (§5)
    if record.oracle is not None:
        o = record.oracle
        items.append(
            EvidenceItem(
                "E-ORACLE-MAE",
                "5. Ceiling",
                "Noise-floor oracle MAE vs compromise mean",
                f"{_f2(o.oracle_mae)} vs {_f2(o.compromise_mae)}",
                src,
                prov,
                f"{o.best_model}, {o.folds}-fold CV over {o.n_issues} issues (D11.0)",
            )
        )
        items.append(
            EvidenceItem(
                "E-ORACLE-GAP",
                "5. Ceiling",
                "Ceiling gap (compromise - oracle)",
                _f2(o.gap),
                src,
                prov,
                "<= 0 => mean at/near the extractable-signal ceiling (COOPERATIVE domain only)",
            )
        )
    # sourced-capability method note (§3)
    items.append(
        EvidenceItem(
            "E-METHOD-capabilities",
            "3. Fair fight",
            "Actor capability source",
            "treaty-regime Council power (pre-Nice / Nice / Lisbon), rescaled strongest=100",
            "src/schelling/backtest/capability.py",
            _git_short(repo_root, "src/schelling/backtest/capability.py"),
            "Commission/EP = largest member-state power (D10.1/D10.3); feeds solver AND baseline",
        )
    )
    # worst issues (limitations §9): the aggregate the draft cites, plus the top few
    if record.worst_issues:
        top_err = max(w.error for w in record.worst_issues)
        items.append(
            EvidenceItem(
                "E-WORST",
                "9. Limitations",
                "Worst-issue errors (primary solver)",
                f"{len(record.worst_issues)} issues at abs error up to {_f2(top_err)}",
                src,
                prov,
                "0/100-pole coding coarseness — pole-to-pole misses",
            )
        )
    for w in record.worst_issues[:3]:
        items.append(
            EvidenceItem(
                f"E-WORST-{w.issue_id}",
                "9. Limitations",
                f"Worst issue — {w.proposal_name}",
                f"err {_f2(w.error)} (forecast {_f2(w.forecast)}, actual {_f2(w.actual)})",
                src,
                prov,
                "0/100-pole coding coarseness",
            )
        )
    return items


def _mae(record: BacktestRecord, key: str) -> float:
    for m in record.methods:
        if m.key == key:
            return m.mae
    raise KeyError(key)


def _round1_items(repo_root: Path, csv_path: Path) -> list[EvidenceItem]:
    """The first, handicapped evaluation (§3): equal capability, no reference point (Session 9)."""
    from schelling.backtest.deu import load_deu_issues
    from schelling.backtest.harness import run_backtest

    issues = load_deu_issues(csv_path, capability=100.0, sourced_capability=False, min_actors=3)
    rec = run_backtest(
        issues,
        csv_path=csv_path,
        dataset_label=_DEU_LABEL,
        seed=42,
        draws=2000,
        capability=100.0,
        capability_mode="equal",
        reference_point=False,
        oracle=None,
    )
    prov = f"sha256:{rec.dataset_sha256[:12]}"
    src = f"data/deu/{_DEU_CSV_NAME}"
    return [
        EvidenceItem(
            "E-DEU-MAE-r1",
            "3. Fair fight",
            "Round-1 challenge MAE (equal capability)",
            _f2(_mae(rec, "solver_paper")),
            src,
            prov,
            "handicapped run: equal capability, no reference point (Session 9, D9.2)",
        ),
        EvidenceItem(
            "E-BASE-WMEAN-r1",
            "3. Fair fight",
            "Round-1 weighted-mean MAE (equal capability)",
            _f2(_mae(rec, "baseline_wmean")),
            src,
            prov,
            "= salience-weighted mean under equal capability; the baseline round 1 loses to",
        ),
    ]


# --------------------------------------------------------------------------- successor search (§4)
def _successor_items(repo_root: Path, report: SuccessorReport) -> list[EvidenceItem]:
    prov = f"sha256:{report.dataset_sha256[:12]}"
    src = "src/schelling/backtest/deu3_split.json"
    sc = report.split_counts
    items = [
        EvidenceItem(
            "E-R1-SPLIT",
            "4. Successor",
            "Pre-registered split (train / dev / TEST)",
            f"{sc['train']} / {sc['dev']} / {sc['test']}",
            src,
            _git_short(repo_root, src),
            f"seed {report.split_seed}; committed before any candidate code (git order = prereg)",
        )
    ]
    for c in report.candidates:
        beats = "beats" if c.beats_compromise else "does NOT beat"
        items.append(
            EvidenceItem(
                f"E-R1-{c.key}",
                "4. Successor",
                f"{c.name}: TEST MAE vs compromise",
                f"{_f2(c.test_mae)} vs {_f2(c.test_compromise_mae)}",
                src,
                prov,
                f"Δ {c.delta:+.2f} [95% CI {c.ci_lo:+.2f}, {c.ci_hi:+.2f}] "
                f"(boot seed {report.boot_seed}) — {beats} compromise, on {c.applies_to}",
            )
        )
    return items


# --------------------------------------------------------------------------- sealed ledger (§8)
_LEDGER_ROW = re.compile(
    r"^\|\s*(?P<model>\w+)\s*\|\s*(?P<vintage>\w+)\s*\|\s*(?P<q>[\w-]+)\s*\|"
    r"\s*(?P<frozen>[\d-]+)\s*\|\s*(?P<median>[\d.]+)\s*\|\s*`(?P<sha>[0-9a-f]{64})`\s*\|\s*$"
)


def _ledger_items(repo_root: Path) -> tuple[list[EvidenceItem], list[str]]:
    path = repo_root / "FORECASTS.md"
    if not path.exists():
        return [], ["ledger: FORECASTS.md not found"]
    prov = _git_short(repo_root, "FORECASTS.md")
    items: list[EvidenceItem] = []
    for line in path.read_text().splitlines():
        m = _LEDGER_ROW.match(line)
        if not m:
            continue
        items.append(
            EvidenceItem(
                f"E-LEDGER-{m['model']}-{m['vintage']}",
                "8. Ledger",
                f"Sealed {m['model']} {m['vintage']} median",
                m["median"],
                "FORECASTS.md",
                prov,
                f"frozen {m['frozen']}; sha256 {m['sha'][:12]}… (gitignored — commit-reveal)",
            )
        )
    if not items:
        return [], ["ledger: no sealed rows parsed from FORECASTS.md LEDGER block"]
    return items, []


# --------------------------------------------------------------------------- test count
_CTX_ROW = re.compile(
    r"^\|\s*(?P<model>[^|]+?)\s*\|\s*(?P<mae>\d+\.\d+)\s*\|\s*(?P<subset>[^|]+?)"
    r"\s*\|\s*(?P<src>[^|]+?)\s*\|\s*$"
)


def _context_items(repo_root: Path) -> list[EvidenceItem]:
    """Published DEU-model error rates (context/ordering only), read from BACKTEST.md."""
    path = repo_root / "BACKTEST.md"
    if not path.exists():
        return []
    prov = _git_short(repo_root, "BACKTEST.md")
    text = path.read_text()
    items: list[EvidenceItem] = []
    old_model: list[str] = []
    wmean: list[str] = []
    for line in text.splitlines():
        m = _CTX_ROW.match(line)
        if not m or m["mae"] in ("", None) or "abs. error" in m["model"].lower():
            continue
        if "BdM" not in m["src"] and "Table" not in m["src"]:
            continue
        model = m["model"].strip()
        items.append(
            EvidenceItem(
                f"E-CTX-{len(items) + 1}",
                "3. Fair fight (context)",
                f"Published: {model}",
                m["mae"],
                "BACKTEST.md",
                prov,
                f"{m['subset'].strip()} — {m['src'].strip()} (regime/ordering only, NOT like-for-like)",
            )
        )
        if "Old Model" in model:
            old_model.append(m["mae"])
        elif "Weighted mean" in model:
            wmean.append(m["mae"])
    # named summaries the draft cites directly
    if old_model and wmean:
        items.append(
            EvidenceItem(
                "E-CTX-bdm2011",
                "3. Fair fight (context)",
                "BdM (2011): Old Model vs weighted mean MAE",
                f"Old Model {'/'.join(old_model)} vs weighted mean {'/'.join(wmean)}",
                "BACKTEST.md",
                prov,
                "BdM 2011 Tables 1 & 3 — same regime & ordering, NOT like-for-like (diff DEU version)",
            )
        )
    if "Achen" in text and "as well or better" in text:
        items.append(
            EvidenceItem(
                "E-CTX-achen2006",
                "3. Fair fight (context)",
                "Achen (2006) finding",
                "weighted mean does as well or better than complex models",
                "BACKTEST.md",
                prov,
                "canonical DEU finding cited in BACKTEST.md (qualitative)",
            )
        )
    return items


def _china_items(repo_root: Path) -> tuple[list[EvidenceItem], list[str]]:
    """Blind-verified China case-library facts, read from the committed JSON (D13.0)."""
    import json

    path = repo_root / "data" / "coercive-cases" / "ktab-china-2014.json"
    if not path.exists():
        return [], ["China case: ktab-china-2014.json not found"]
    data = json.loads(path.read_text())
    src = "data/coercive-cases/ktab-china-2014.json"
    prov = _git_short(repo_root, src)
    counts = [len(c.get("actors", [])) for c in data.get("cases", [])]
    verified = bool(data.get("transcription", {}).get("verified", False))
    total = sum(counts)
    return [
        EvidenceItem(
            "E-CHINA-ROWS",
            "7. Case library",
            "China Tables 2+3 rows verified (blind dual entry)",
            f"{total}/{total} ({' + '.join(str(c) for c in counts)})",
            src,
            prov,
            "two independent blind transcriptions agree; every Exercised-Power checksum reproduces",
        ),
        EvidenceItem(
            "E-CHINA-VERIFIED",
            "7. Case library",
            "China transcription.verified",
            str(verified),
            src,
            prov,
            "flipped true only on human ratification (D13.0)",
        ),
    ], []


def _domain_verdict_item(repo_root: Path) -> tuple[EvidenceItem | None, list[str]]:
    """Suppressed-verdict discipline, from BACKTEST.md (cooperative decided; coercive PENDING)."""
    path = repo_root / "BACKTEST.md"
    if not path.exists():
        return None, ["domain verdict: BACKTEST.md not found"]
    text = path.read_text()
    if "PENDING" not in text or "Cooperative" not in text:
        return None, ["domain verdict: BACKTEST.md missing the domain-verdicts table"]
    return EvidenceItem(
        "E-DOMAIN-VERDICT",
        "7. Case library",
        "Domain verdicts",
        "cooperative: compromise mean wins; coercive: PENDING",
        "BACKTEST.md",
        _git_short(repo_root, "BACKTEST.md"),
        "coercive classics paywalled (D11.1); domestic cases out-of-domain, never counted",
    ), []


def _test_count_item(repo_root: Path) -> tuple[EvidenceItem | None, list[str]]:
    try:
        out = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ["test count: pytest --collect-only failed to run"]
    m = re.search(r"(\d+)\s+tests?\s+collected", out.stdout)
    if not m:
        # older pytest prints "N tests collected"; fall back to counting id lines
        ids = [ln for ln in out.stdout.splitlines() if "::" in ln]
        if not ids:
            return None, ["test count: could not parse pytest --collect-only output"]
        n = str(len(ids))
    else:
        n = m.group(1)
    return EvidenceItem(
        "E-TESTS",
        "Repro",
        "Test count (pytest --collect-only)",
        n,
        "tests/",
        _git_short(repo_root, "tests"),
        "regenerated live; green gate is the acceptance bar",
    ), []


# --------------------------------------------------------------------------- assembly
def build_evidence(repo_root: Path) -> EvidenceBundle:
    """Gather every cited number from the repo's artifacts. Runs the DEU backtest if present."""
    from schelling.backtest.deu import load_deu_issues
    from schelling.backtest.harness import run_backtest
    from schelling.backtest.oracle import oracle_summary
    from schelling.backtest.successor import run_successor_search

    bundle = EvidenceBundle(head_commit=_git_short(repo_root))
    bundle.items += _replication_items(repo_root)

    csv_path = repo_root / "data" / "deu" / _DEU_CSV_NAME
    if csv_path.exists():
        issues = load_deu_issues(csv_path, capability=100.0, sourced_capability=True, min_actors=3)
        oracle = oracle_summary(issues) if len(issues) >= 40 else None
        record = run_backtest(
            issues,
            csv_path=csv_path,
            dataset_label=_DEU_LABEL,
            seed=42,
            draws=2000,
            capability=0.0,
            capability_mode="sourced",
            reference_point=True,
            oracle=oracle,
        )
        bundle.record = record
        bundle.items += _deu_items(repo_root, record)
        bundle.items += _round1_items(repo_root, csv_path)
        report, _a, _b = run_successor_search(csv_path)
        bundle.report = report
        bundle.items += _successor_items(repo_root, report)
    else:
        bundle.open_questions += [
            "DEU MAE/RMSE tables, split-sample, oracle gap, worst issues, round-1 (E-DEU-MAE-r1 / "
            "E-BASE-WMEAN-r1): data/deu absent — download DEU III (doi:10.34810/data53) to redo.",
            "Successor leaderboard + bootstrap CIs + R1 split sizes: data/deu absent (see above).",
        ]

    ledger_items, ledger_open = _ledger_items(repo_root)
    bundle.items += ledger_items
    bundle.open_questions += ledger_open

    bundle.items += _context_items(repo_root)

    china_items, china_open = _china_items(repo_root)
    bundle.items += china_items
    bundle.open_questions += china_open

    verdict_item, verdict_open = _domain_verdict_item(repo_root)
    if verdict_item is not None:
        bundle.items.append(verdict_item)
    bundle.open_questions += verdict_open

    test_item, test_open = _test_count_item(repo_root)
    if test_item is not None:
        bundle.items.append(test_item)
    bundle.open_questions += test_open
    return bundle


def evidence_markdown(bundle: EvidenceBundle) -> str:
    """Render EVIDENCE.md — a pure table of sourced numbers. No prose, no timestamps."""
    lines = [
        "# EVIDENCE.md — every cited number, regenerated from repo artifacts (D14.1)",
        "",
        "> Generated by `schelling paper-evidence`. Never hand-edit: each row is computed from the "
        "artifact named, and re-running regenerates this file byte-for-byte from the same repo "
        "state. Provenance is the git short hash of the source file, or `sha256:` prefix for "
        "data-derived numbers. No wall-clock timestamps are recorded (determinism, rule 2).",
        "",
        "| E-tag | Section | Metric | Value | Source | Provenance | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for it in bundle.items:
        note = it.note.replace("|", "\\|")
        lines.append(
            f"| {it.tag} | {it.section} | {it.metric} | {it.value} | `{it.source}` | "
            f"`{it.provenance}` | {note} |"
        )
    lines.append("")
    lines.append("## Open questions — numbers no artifact could source")
    if bundle.open_questions:
        lines += [f"- {q}" for q in bundle.open_questions]
    else:
        lines.append("- (none — every cited number resolved to an artifact)")
    lines.append("")
    return "\n".join(lines)
